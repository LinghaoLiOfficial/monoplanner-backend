"""Requirement-text prompt-pack evaluation with isolated target labels.

This protocol accepts the compact Markdown release received for this study.  It
does not convert target labels into prompt input and deliberately does not
pretend to implement the asset-snapshot/full-orchestration protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.storage import digest, now, read_json, write_new
from evals.transport import RecordedGenerator, public_config

CHAIN = re.compile(r"^# (chain-\d{2})$")
STEP = re.compile(r"^## (c\d{2}-s[123])$")
CELL = re.compile(r"^\| ([^|]+) \| (.+) \|$")
FACT = re.compile(r"^\| ([a-z0-9-]+) \| `([^`]+)` \| (.+) \| `([^`]+)` \|$")
TOPICS = (
    "item_validation",
    "pagination",
    "permissions",
    "field_rename",
    "null_and_clear",
    "error_contract",
    "filter_sort",
    "delete_restore",
    "user_profile",
    "scope_clarification",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Label(Strict):
    fact_id: str = Field(pattern=r"^[a-z0-9-]+$")
    target: str = Field(min_length=1)
    value: object
    sources: list[str] = Field(min_length=1)


class RequirementStep(Strict):
    step_id: str = Field(pattern=r"^c\d{2}-s[123]$")
    required_sides: list[Literal["frontend", "backend"]] = Field(min_length=1, max_length=2)
    raw_requirement: str = Field(min_length=1)
    preserved_constraints: str = Field(min_length=1)
    labels: list[Label] = Field(min_length=1)

    @model_validator(mode="after")
    def ids_are_unique(self):
        if len(set(self.required_sides)) != len(self.required_sides):
            raise ValueError("required_sides contains duplicates")
        if len({label.fact_id for label in self.labels}) != len(self.labels):
            raise ValueError("labels contain duplicate fact_id")
        return self


class RequirementChain(Strict):
    chain_id: str = Field(pattern=r"^chain-\d{2}$")
    topic: str
    split: Literal["dev", "test"]
    requirement_origin: Literal["designed_scenario", "repository_history"]
    steps: list[RequirementStep] = Field(min_length=3, max_length=3)


class RequirementDataset(Strict):
    schema_version: Literal["requirement-labels-v1"]
    dataset_id: str
    source_document: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    chains: list[RequirementChain] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def complete_layout(self):
        if tuple(chain.topic for chain in self.chains) != TOPICS:
            raise ValueError("Unexpected topic layout")
        ids = [step.step_id for chain in self.chains for step in chain.steps]
        if len(set(ids)) != 30:
            raise ValueError("Expected 30 unique steps")
        for index, chain in enumerate(self.chains, 1):
            if chain.chain_id != f"chain-{index:02d}" or chain.split != (
                "dev" if index <= 2 else "test"
            ):
                raise ValueError("Unexpected chain ID or split")
        return self


class PromptSection(Strict):
    needed: bool
    prompt: str


class RequirementPack(Strict):
    frontend: PromptSection
    backend: PromptSection


class ReviewEvidence(Strict):
    side: Literal["frontend", "backend"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class FactAssessment(Strict):
    fact_id: str = Field(min_length=1)
    label: Literal["consistent", "contradiction", "omission", "uncertain", "common_error"]
    explanation: str = Field(min_length=1)
    evidence: list[ReviewEvidence] = Field(default_factory=list)


class PackReview(Strict):
    blind_id: str = Field(pattern=r"^packet-\d{3}$")
    pack_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    assessments: list[FactAssessment]


class ReviewFile(Strict):
    schema_version: Literal["requirement-review-v1"]
    reviewer: str = Field(min_length=1)
    human_attestation: Literal[True]
    reviews: list[PackReview]


def parse_markdown(source: Path) -> RequirementDataset:
    raw = source.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    chains = []
    chain: dict | None = None
    step: dict | None = None
    mode = ""
    for line_number, line in enumerate(lines, 1):
        match = CHAIN.fullmatch(line)
        if match:
            if chain:
                chains.append(chain)
            chain = {"chain_id": match.group(1), "steps": []}
            step = None
            mode = "chain"
            continue
        match = STEP.fullmatch(line)
        if match:
            if chain is None:
                raise ValueError(f"line {line_number}: step without chain")
            step = {"step_id": match.group(1), "labels": []}
            chain["steps"].append(step)
            mode = "step"
            continue
        if not chain:
            continue
        if mode == "chain" and line.startswith("| chain_id | topic | split | requirement_origin |"):
            continue
        if mode == "chain" and line.startswith("| ---"):
            continue
        if mode == "chain" and line.startswith("| chain-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) != 4:
                raise ValueError(f"line {line_number}: invalid chain row")
            chain.update(
                dict(zip(("chain_id", "topic", "split", "requirement_origin"), cells, strict=True))
            )
            continue
        if step is None:
            continue
        if line.startswith("| fact_id |"):
            mode = "facts"
            continue
        if line.startswith("| 字段 |") or (mode == "step" and line.startswith("| ---")):
            continue
        if mode == "facts":
            if not line.startswith("|") or line.startswith("| ---"):
                continue
            fact = FACT.fullmatch(line)
            if not fact:
                raise ValueError(f"line {line_number}: invalid fact row")
            fact_id, target, raw_value, sources = fact.groups()
            try:
                value = json.loads(raw_value.strip("`"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON label value") from exc
            step["labels"].append(
                {"fact_id": fact_id, "target": target, "value": value, "sources": [sources]}
            )
            continue
        cell = CELL.fullmatch(line)
        if cell:
            key, value = cell.groups()
            if key == "step_id":
                if value != step["step_id"]:
                    raise ValueError(f"line {line_number}: step ID mismatch")
            elif key == "required_sides":
                step[key] = json.loads(value.strip("`"))
            elif key == "raw_requirement":
                step[key] = value
            elif key == "preserved_constraints / acceptance_criteria":
                step["preserved_constraints"] = value
    if chain:
        chains.append(chain)
    return RequirementDataset.model_validate(
        {
            "schema_version": "requirement-labels-v1",
            "dataset_id": "monoplanner-new-data-v1",
            "source_document": source.name,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "chains": chains,
        }
    )


def write_release(source: Path, output: Path) -> RequirementDataset:
    dataset = parse_markdown(source)
    write_new(output, dataset.model_dump(mode="json"))
    return dataset


def message(step: RequirementStep) -> str:
    return "\n\n".join(
        (
            "需求：" + step.raw_requirement,
            "持续有效约束与验收条件：" + step.preserved_constraints,
            "生成要求：只输出实施指令；不得使用未提供的历史信息；不要猜测未决契约。",
        )
    )


def rule_pack(step: RequirementStep) -> RequirementPack:
    payload = message(step)
    return RequirementPack(
        **{
            side: {
                "needed": side in step.required_sides,
                "prompt": payload
                if side in step.required_sides
                else "No changes required on this side.",
            }
            for side in ("frontend", "backend")
        }
    )


def independent_pack(step: RequirementStep, generator: RecordedGenerator) -> RequirementPack:
    sections = {}
    for side in ("frontend", "backend"):
        sections[side] = generator(
            f"Generate {side} implementation instructions only. Decide scope from the requirement. "
            "Do not use another side's output. Cover every applicable requirement and preserved "
            "constraint explicitly, including unchanged shared API facts; do not omit a fact "
            "merely because it is implemented by the other side.",
            message(step),
            response_model=PromptSection,
            task_key="prompt_pack",
        )
    return RequirementPack(**sections)


def joint_pack(step: RequirementStep, generator: RecordedGenerator) -> RequirementPack:
    return RequirementPack(
        **generator(
            "Generate synchronized frontend and backend implementation instructions. "
            "Decide required scope from the requirement. "
            "Do not invent unresolved contract decisions. First enumerate every explicit contract "
            "fact from the requirement and preserved constraints; repeat each shared fact clearly "
            "in both applicable side prompts, and state any side-specific omission explicitly.",
            message(step),
            response_model=RequirementPack,
            task_key="prompt_pack",
        )
    )


def run(
    dataset_path: Path,
    output: Path,
    split: str,
    repeats: int,
    workers: int = 1,
    methods: tuple[str, ...] = ("rule", "independent", "joint"),
) -> None:
    data = RequirementDataset.model_validate(read_json(dataset_path))
    if repeats < 1 or repeats > 3:
        raise ValueError("repeats must be between 1 and 3")
    if workers < 1 or workers > 8:
        raise ValueError("workers must be between 1 and 8")
    allowed_methods = {"rule", "independent", "joint"}
    if not methods or len(set(methods)) != len(methods) or set(methods) - allowed_methods:
        raise ValueError("methods must contain distinct supported methods")
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "dataset.json", data.model_dump(mode="json"))
    write_new(
        output / "manifest.json",
        {
            "protocol": "requirement-direct-v1",
            "created_at": now(),
            "split": split,
            "dataset_sha256": digest(data.model_dump(mode="json")),
            "model_config": public_config("prompt_pack"),
            "methods": list(methods),
            "repeats": repeats,
            "workers": workers,
            "labels_excluded_from_generation": True,
            "fullchain": "not_run_missing_asset_snapshots",
        },
    )
    jobs = [
        (chain.chain_id, step, method, repeat)
        for chain in data.chains
        if chain.split == split
        for step in chain.steps
        for method in methods
        for repeat in range(1, repeats + 1)
    ]

    def execute(job) -> str:
        chain_id, step, method, repeat = job
        unit_id = f"{chain_id}-{step.step_id}-{method}-r{repeat}"
        directory = output / "units" / unit_id
        write_new(
            directory / "input.json",
            {
                "chain_id": chain_id,
                "step_id": step.step_id,
                "required_sides": step.required_sides,
                "raw_requirement": step.raw_requirement,
                "preserved_constraints": step.preserved_constraints,
            },
        )
        generator = RecordedGenerator(directory / "calls")
        try:
            pack = (
                rule_pack(step)
                if method == "rule"
                else (
                    independent_pack(step, generator)
                    if method == "independent"
                    else joint_pack(step, generator)
                )
            )
            write_new(directory / "pack.json", pack.model_dump())
            write_new(
                directory / "outcome.json",
                {
                    "status": "completed",
                    "pack_sha256": digest(pack.model_dump()),
                    "calls": generator.calls,
                },
            )
            return "completed"
        except Exception as exc:
            write_new(
                directory / "outcome.json",
                {
                    "status": "generation_failed",
                    "error_type": type(exc).__name__,
                    "calls": generator.calls,
                },
            )
            return "generation_failed"

    summary = Counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(execute, job) for job in jobs]
        for future in as_completed(futures):
            summary[future.result()] += 1
    write_new(output / "completed.json", {"completed_at": now(), **summary})


def _review_template(run_path: Path) -> tuple[list[dict], dict[str, dict]]:
    dataset = RequirementDataset.model_validate(read_json(run_path / "dataset.json"))
    steps = {step.step_id: step for chain in dataset.chains for step in chain.steps}
    packets = []
    key = {}
    for outcome_path in sorted((run_path / "units").glob("*/outcome.json")):
        pack_path = outcome_path.parent / "pack.json"
        if not pack_path.exists():
            continue
        unit_id = outcome_path.parent.name
        input_value = read_json(outcome_path.parent / "input.json")
        step = steps[input_value["step_id"]]
        pack = RequirementPack.model_validate(read_json(pack_path))
        packets.append(
            {
                "unit_id": unit_id,
                "pack_sha256": digest(pack.model_dump()),
                "raw_requirement": input_value["raw_requirement"],
                "preserved_constraints": input_value["preserved_constraints"],
                "required_sides": input_value["required_sides"],
                "facts": [label.model_dump(mode="json") for label in step.labels],
                "frontend_prompt": pack.frontend.prompt,
                "backend_prompt": pack.backend.prompt,
            }
        )
    return packets, key


def export_reviews(run_path: Path, output: Path) -> dict:
    """Create shuffled review packets without exposing experimental-arm identities."""
    packets, _ = _review_template(run_path)
    seed = int(
        hashlib.sha256(digest([item["pack_sha256"] for item in packets]).encode()).hexdigest(), 16
    )
    random.Random(seed).shuffle(packets)
    blind_key = {}
    reviews = []
    public_packets = []
    for index, packet in enumerate(packets, 1):
        blind_id = f"packet-{index:03d}"
        blind_key[blind_id] = {"unit_id": packet.pop("unit_id")}
        public_packets.append({"blind_id": blind_id, **packet})
        reviews.append(
            {
                "blind_id": blind_id,
                "pack_sha256": packet["pack_sha256"],
                "assessments": [
                    {
                        "fact_id": fact["fact_id"],
                        "label": "",
                        "explanation": "",
                        "evidence": [],
                    }
                    for fact in packet["facts"]
                ],
            }
        )
    output.mkdir(parents=True, exist_ok=False)
    write_new(
        output / "packets.json",
        {"schema_version": "requirement-review-packets-v1", "packets": public_packets},
    )
    write_new(
        output / "blind-key.json",
        {"schema_version": "requirement-blind-key-v1", "mapping": blind_key},
    )
    write_new(
        output / "reviews.template.json",
        {
            "schema_version": "requirement-review-v1",
            "reviewer": "",
            "human_attestation": False,
            "reviews": reviews,
        },
    )
    return {"packets": len(public_packets), "output": str(output)}


def _score_review(pack: RequirementPack, step: RequirementStep, review: PackReview) -> dict:
    if review.pack_sha256 != digest(pack.model_dump()):
        raise ValueError("Review does not match pack hash")
    expected = {label.fact_id for label in step.labels}
    observed = {assessment.fact_id for assessment in review.assessments}
    if expected != observed or len(observed) != len(review.assessments):
        raise ValueError("Each required fact must be assessed exactly once")
    counts = Counter()
    for assessment in review.assessments:
        sides = set()
        for evidence in assessment.evidence:
            text = getattr(pack, evidence.side).prompt
            if text[evidence.start : evidence.end] != evidence.quote:
                raise ValueError("Evidence quote must match the stated prompt offsets")
            sides.add(evidence.side)
        if assessment.label in {"contradiction", "common_error"} and sides != {
            "frontend",
            "backend",
        }:
            raise ValueError("Contradiction and common-error labels require both-side evidence")
        if assessment.label == "consistent" and not set(step.required_sides) <= sides:
            raise ValueError("Consistent labels require evidence for every required side")
        counts[assessment.label] += 1
    evaluable = counts["omission"] == counts["uncertain"] == 0
    return {
        "status": "evaluated" if evaluable else "not_evaluable",
        "C": counts["contradiction"] if evaluable else None,
        "valid_zero": evaluable and counts["contradiction"] == counts["common_error"] == 0,
        "label_counts": dict(counts),
    }


def report(run_path: Path, output: Path, reviews_path: Path | None = None) -> dict:
    manifest = read_json(run_path / "manifest.json")
    dataset = RequirementDataset.model_validate(read_json(run_path / "dataset.json"))
    steps = {step.step_id: step for chain in dataset.chains for step in chain.steps}
    planned_units = (
        sum(len(chain.steps) for chain in dataset.chains if chain.split == manifest["split"])
        * len(manifest["methods"])
        * manifest["repeats"]
    )
    review_mapping = {}
    review_identity = None
    if reviews_path:
        review_file = ReviewFile.model_validate(read_json(reviews_path))
        review_identity = {"reviewer": review_file.reviewer, "human_attestation": True}
        key = read_json(run_path / "review" / "blind-key.json")["mapping"]
        for review in review_file.reviews:
            unit_id = key.get(review.blind_id, {}).get("unit_id")
            if not unit_id or unit_id in review_mapping:
                raise ValueError("Review contains an unknown or duplicate blind ID")
            review_mapping[unit_id] = review
    rows = []
    usage = []
    for path in sorted((run_path / "units").glob("*/outcome.json")):
        outcome = read_json(path)
        unit = path.parent.name
        pack_path = path.parent / "pack.json"
        structural = []
        if pack_path.exists():
            pack = RequirementPack.model_validate(read_json(pack_path))
            input_value = read_json(path.parent / "input.json")
            expected = set(input_value["required_sides"])
            actual = {side for side in ("frontend", "backend") if getattr(pack, side).needed}
            if expected != actual:
                structural.append("scope_mismatch")
            if any(not getattr(pack, side).prompt.strip() for side in actual):
                structural.append("empty_required_prompt")
        for response in (path.parent / "calls").glob("*.response.json"):
            item = read_json(response)
            if item.get("usage"):
                usage.append(item["usage"])
        row = {
            "unit_id": unit,
            "status": outcome["status"],
            "calls": outcome.get("calls", 0),
            "structural_issues": structural,
        }
        if outcome["status"] == "completed" and not structural and unit in review_mapping:
            input_value = read_json(path.parent / "input.json")
            row["semantic"] = _score_review(
                pack, steps[input_value["step_id"]], review_mapping[unit]
            )
        elif outcome["status"] == "completed" and not structural:
            row["semantic"] = {"status": "pending_review", "C": None, "valid_zero": False}
        else:
            row["semantic"] = {"status": "invalid_pack", "C": None, "valid_zero": False}
        rows.append(row)
    counts = Counter(row["status"] for row in rows)
    structural = Counter(issue for row in rows for issue in row["structural_issues"])
    semantic_rows = [row["semantic"] for row in rows]
    reviewed = [item for item in semantic_rows if item["status"] in {"evaluated", "not_evaluable"}]
    evaluated = [item for item in reviewed if item["status"] == "evaluated"]
    all_labels = sum((Counter(item.get("label_counts", {})) for item in reviewed), Counter())
    assessed_facts = sum(all_labels.values())
    semantic_metrics = {
        "C_total": sum(item["C"] for item in evaluated) if reviewed else None,
        "observed_C_total": all_labels["contradiction"] if reviewed else None,
        "C_mean": (sum(item["C"] for item in evaluated) / len(evaluated)) if evaluated else None,
        "valid_zero_rate": (sum(item["valid_zero"] for item in semantic_rows) / len(rows))
        if reviewed
        else None,
        "reviewed_units": len(reviewed),
        "evaluable_units": len(evaluated),
        "evaluable_rate": len(evaluated) / planned_units if planned_units else None,
        "invalid_pack_units": sum(item["status"] == "invalid_pack" for item in semantic_rows),
        "not_evaluable_units": sum(item["status"] == "not_evaluable" for item in semantic_rows),
        "assessed_facts": assessed_facts,
        "label_counts": dict(all_labels),
        "fact_omission_rate": (all_labels["omission"] / assessed_facts if assessed_facts else None),
        "fact_uncertain_rate": (
            all_labels["uncertain"] / assessed_facts if assessed_facts else None
        ),
        "fact_common_error_rate": (
            all_labels["common_error"] / assessed_facts if assessed_facts else None
        ),
        "pending_review_units": sum(item["status"] == "pending_review" for item in semantic_rows),
        "status": "complete"
        if len(rows) == planned_units
        and len(reviewed) + sum(item["status"] == "invalid_pack" for item in semantic_rows)
        == planned_units
        else "requires_blind_semantic_review",
    }
    result = {
        "created_at": now(),
        "protocol": manifest["protocol"],
        "model_config": manifest["model_config"],
        "planned_prompt_pack_units": planned_units,
        "completed_units": counts["completed"],
        "failed_units": counts["generation_failed"],
        "total_model_calls": sum(row["calls"] for row in rows),
        "structural_issue_counts": dict(structural),
        "semantic_metrics": semantic_metrics,
        "review": review_identity,
        "fullchain": manifest["fullchain"],
        "usage_records": usage,
        "units": rows,
    }
    by_method = {}
    for row in rows:
        method = row["unit_id"].rsplit("-r", 1)[0].rsplit("-", 1)[-1]
        bucket = by_method.setdefault(method, [])
        bucket.append(row)
    result["method_summary"] = {
        method: {
            "planned_units": len(method_rows),
            "evaluable_units": sum(row["semantic"]["status"] == "evaluated" for row in method_rows),
            "invalid_pack_units": sum(
                row["semantic"]["status"] == "invalid_pack" for row in method_rows
            ),
            "not_evaluable_units": sum(
                row["semantic"]["status"] == "not_evaluable" for row in method_rows
            ),
            "C_total": sum(
                row["semantic"]["C"]
                for row in method_rows
                if row["semantic"]["status"] == "evaluated"
            ),
            "observed_C_total": sum(
                row["semantic"].get("label_counts", {}).get("contradiction", 0)
                for row in method_rows
            ),
            "valid_zero_units": sum(
                row["semantic"].get("valid_zero", False) for row in method_rows
            ),
            "label_counts": dict(
                sum(
                    (Counter(row["semantic"].get("label_counts", {})) for row in method_rows),
                    Counter(),
                )
            ),
        }
        for method, method_rows in by_method.items()
    }
    pairs: dict[str, dict[str, dict]] = {}
    for row in rows:
        match = re.fullmatch(r"(.+)-(rule|independent|joint)-(r\d+)", row["unit_id"])
        if match:
            pair_id, method, repeat = match.groups()
            pairs.setdefault(f"{pair_id}-{repeat}", {})[method] = row
    rule_joint_pairs = [pair for pair in pairs.values() if {"rule", "joint"} <= set(pair)]
    if rule_joint_pairs:
        result["paired_rule_vs_joint"] = {
            "pairs": len(rule_joint_pairs),
            "joint_strict_wins": sum(
                pair["joint"]["semantic"].get("valid_zero", False)
                and not pair["rule"]["semantic"].get("valid_zero", False)
                for pair in rule_joint_pairs
            ),
            "rule_strict_wins": sum(
                pair["rule"]["semantic"].get("valid_zero", False)
                and not pair["joint"]["semantic"].get("valid_zero", False)
                for pair in rule_joint_pairs
            ),
            "strict_ties": sum(
                pair["rule"]["semantic"].get("valid_zero", False)
                == pair["joint"]["semantic"].get("valid_zero", False)
                for pair in rule_joint_pairs
            ),
            "joint_minus_rule_omissions": sum(
                pair["joint"]["semantic"].get("label_counts", {}).get("omission", 0)
                - pair["rule"]["semantic"].get("label_counts", {}).get("omission", 0)
                for pair in rule_joint_pairs
            ),
            "joint_minus_rule_observed_contradictions": sum(
                pair["joint"]["semantic"].get("label_counts", {}).get("contradiction", 0)
                - pair["rule"]["semantic"].get("label_counts", {}).get("contradiction", 0)
                for pair in rule_joint_pairs
            ),
        }
    write_new(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("source", type=Path)
    extract.add_argument("output", type=Path)
    generate = sub.add_parser("generate")
    generate.add_argument("dataset", type=Path)
    generate.add_argument("output", type=Path)
    generate.add_argument("--split", choices=("dev", "test"), required=True)
    generate.add_argument("--repeats", type=int, default=1)
    generate.add_argument("--workers", type=int, default=1)
    generate.add_argument(
        "--methods",
        nargs="+",
        choices=("rule", "independent", "joint"),
        default=("rule", "independent", "joint"),
    )
    review_export = sub.add_parser("review-export")
    review_export.add_argument("run", type=Path)
    review_export.add_argument("output", type=Path)
    summary = sub.add_parser("report")
    summary.add_argument("run", type=Path)
    summary.add_argument("output", type=Path)
    summary.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    if args.command == "extract":
        dataset = write_release(args.source, args.output)
        print(json.dumps({"chains": len(dataset.chains), "steps": 30}, ensure_ascii=False))
    elif args.command == "generate":
        run(
            args.dataset,
            args.output,
            args.split,
            args.repeats,
            args.workers,
            tuple(args.methods),
        )
    elif args.command == "review-export":
        print(json.dumps(export_reviews(args.run, args.output), ensure_ascii=False))
    else:
        print(json.dumps(report(args.run, args.output, args.reviews), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
