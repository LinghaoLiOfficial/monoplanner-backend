from __future__ import annotations

import secrets
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from evals.dataset import Answers
from evals.scoring import Review, score
from evals.storage import digest, now, read_json, write_new


def export_reviews(run: Path, answers_path: Path, output: Path) -> None:
    manifest = read_json(run / "manifest.json")
    answers = Answers.model_validate(read_json(answers_path))
    if digest(answers.model_dump()) != read_json(run / "freeze.json")["answer_sha256"]:
        raise ValueError("Answers changed after freeze")
    data = read_json(run / "inputs.json")
    requirements = {s["step_id"]: s["raw_requirement"] for c in data["chains"] for s in c["steps"]}
    planned = list(manifest["planned"])
    secrets.SystemRandom().shuffle(planned)
    packets = {}
    reviews = {}
    key = {}
    for unit in planned:
        directory = run / "units" / unit["unit_id"]
        if not (directory / "pack.json").exists():
            continue
        pack = read_json(directory / "pack.json")
        review_id = secrets.token_hex(8)
        key[review_id] = {"unit_id": unit["unit_id"], "pack_sha256": digest(pack)}
        packets[review_id] = {
            "requirement": requirements[unit["step_id"]],
            "expected": answers.steps[unit["step_id"]].model_dump(),
            "frontend_prompt": pack["frontend_prompt"],
            "backend_prompt": pack["backend_prompt"],
        }
        reviews[review_id] = Review(pack_sha256=digest(pack)).model_dump()
    # Method identities stay outside the review directory; blinding is not cryptographic.
    write_new(run / "blind-key.json", key)
    write_new(output / "packets.json", packets)
    write_new(output / "reviews.json", {"reviews": reviews})


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["status"] for row in rows)
    measured = [row["C"] for row in rows if row["C"] is not None]
    zeros = sum(row["valid_zero"] for row in rows)
    total = len(rows)
    return {
        "planned": total,
        "valid_zero": zeros,
        "valid_zero_rate": zeros / total if total else None,
        "target_met": zeros / total >= 0.9 if total else False,
        "C_evaluable_n": len(measured),
        "C_total": sum(measured) if measured else None,
        "C_mean": mean(measured) if measured else None,
        "C_distribution": dict(Counter(str(c) for c in measured)),
        "observed_contradictions": sum(row["observed_contradictions"] for row in rows),
        "common_errors": sum(row["common_errors"] for row in rows),
        "statuses": dict(counts),
    }


def report(
    run: Path, answers_path: Path, reviews_path: Path | None, output: Path
) -> dict[str, Any]:
    manifest = read_json(run / "manifest.json")
    lock = read_json(run / "freeze.json")
    data = read_json(run / "inputs.json")
    if digest(data) != lock["input_sha256"]:
        raise ValueError("Run inputs do not match freeze")
    gold_raw = read_json(answers_path)
    if digest(gold_raw) != lock["answer_sha256"]:
        raise ValueError("Answers changed after freeze")
    gold = Answers.model_validate(gold_raw)
    keys = read_json(run / "blind-key.json") if (run / "blind-key.json").exists() else {}
    raw_reviews = read_json(reviews_path)["reviews"] if reviews_path else {}
    if set(raw_reviews) - set(keys):
        raise ValueError("Unknown review IDs")
    by_unit = {}
    for review_id, raw in raw_reviews.items():
        key = keys[review_id]
        review = Review.model_validate(raw)
        if review.pack_sha256 != key["pack_sha256"]:
            raise ValueError("Review pack hash mismatch")
        if key["unit_id"] in by_unit:
            raise ValueError("Duplicate review for unit")
        by_unit[key["unit_id"]] = review
    rows = []
    seen = set()
    for unit in manifest["planned"]:
        if unit["unit_id"] in seen:
            raise ValueError("Duplicate planned unit")
        seen.add(unit["unit_id"])
        directory = run / "units" / unit["unit_id"]
        path = directory / "outcome.json"
        outcome = read_json(path) if path.exists() else {"status": "not_run"}
        pack = read_json(directory / "pack.json") if (directory / "pack.json").exists() else None
        if pack is not None and outcome.get("pack_sha256") != digest(pack):
            raise ValueError("Stored pack changed")
        review = by_unit.get(unit["unit_id"])
        if review is not None and pack is not None and review.pack_sha256 != digest(pack):
            raise ValueError("Review no longer matches stored pack")
        rows.append({**unit, **score(pack, gold.steps[unit["step_id"]], review, outcome["status"])})
    groups = defaultdict(list)
    chains = defaultdict(list)
    for row in rows:
        groups[row["method"]].append(row)
        chains[(row["method"], row["chain_id"], row["repeat"])].append(row)
    chain_rows = [
        {"method": m, "chain_id": c, "repeat": r, **summarize(values)}
        for (m, c, r), values in sorted(chains.items())
    ]
    volatility = []
    for method, chain in sorted({(r["method"], r["chain_id"]) for r in chain_rows}):
        rates = [
            r["valid_zero_rate"]
            for r in chain_rows
            if r["method"] == method and r["chain_id"] == chain
        ]
        volatility.append(
            {"method": method, "chain_id": chain, "repeat_rates": rates, "stddev": pstdev(rates)}
        )
    paired = []
    indexed = {(r["chain_id"], r["step_id"], r["repeat"], r["method"]): r for r in rows}
    for row in rows:
        if row["method"] != "joint":
            continue
        for baseline in ("rule", "independent"):
            other = indexed.get((row["chain_id"], row["step_id"], row["repeat"], baseline))
            comparable = other is not None and row["C"] is not None and other["C"] is not None
            paired.append(
                {
                    "chain_id": row["chain_id"],
                    "step_id": row["step_id"],
                    "repeat": row["repeat"],
                    "baseline": baseline,
                    "C_baseline_minus_joint": other["C"] - row["C"] if comparable else None,
                }
            )
    usage = []
    for path in sorted((run / "units").rglob("*.response.json")):
        value = read_json(path)
        usage.append({"path": str(path.relative_to(run)), "usage": value.get("usage")})
    result = {
        "created_at": now(),
        "split": manifest["split"],
        "overall": summarize(rows),
        "methods": {m: summarize(values) for m, values in sorted(groups.items())},
        "units": rows,
        "chains": chain_rows,
        "repeat_variation": volatility,
        "paired_differences": paired,
        "usage": usage,
        "api_call_count": len(usage),
        "review_sha256": digest(raw_reviews),
        "answer_sha256": lock["answer_sha256"],
        "interpretation": "C statistics exclude unevaluable packs; valid-zero denominator "
        "includes every planned unit. No independent-sample significance claim. "
        "Missing usage/cost is unknown, not zero; no model judge enabled.",
    }
    write_new(output / "report.json", result)
    write_new(output / "review-snapshot.json", {"reviews": raw_reviews})
    return result
