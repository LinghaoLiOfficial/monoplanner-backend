"""v2 contract-fact evaluation for the six development steps."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.requirement_eval import (
    PackReview,
    RequirementDataset,
    RequirementPack,
    parse_markdown,
)
from evals.storage import digest, now, read_json, write_new
from evals.transport import RecordedGenerator, public_config


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContractFact(Strict):
    fact_id: str
    statement: str
    operation: str
    state: str
    category: str
    required_sides: list[Literal["frontend", "backend"]] = Field(min_length=1)
    coverage: Literal["must_be_explicit", "derivable"]
    change_type: Literal["added", "modified", "removed", "rolled_back", "inherited"]
    source_kind: Literal["current_requirement", "inherited"]
    previous_value: object = None
    target_value: object = None
    supersedes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(min_length=1)


class V2Step(Strict):
    step_id: str
    raw_requirement: str
    preserved_constraints: str
    required_sides: list[Literal["frontend", "backend"]]
    change_facts: list[ContractFact]
    active_contract_facts: list[ContractFact]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [fact.fact_id for fact in self.active_contract_facts]
        if len(ids) != len(set(ids)):
            raise ValueError("active contract facts must have unique IDs")
        changes = {fact.fact_id for fact in self.change_facts}
        if not changes <= set(ids):
            raise ValueError("change facts must be active facts")
        return self


class V2Dataset(Strict):
    schema_version: Literal["requirement-contract-v2"]
    dataset_id: str
    source_dataset: str
    chains: dict[str, list[V2Step]]


class AnswerFact(Strict):
    fact_id: str
    expected_value: object
    required_sides: list[Literal["frontend", "backend"]]
    coverage: Literal["must_be_explicit", "derivable"]
    sources: list[str]


class V2Answers(Strict):
    schema_version: Literal["requirement-contract-answers-v2"]
    dataset_id: str
    steps: dict[str, list[AnswerFact]]


def _side_for(target: str) -> list[str]:
    if target.startswith("frontend."):
        return ["frontend"]
    if target.startswith(("database.", "migration.", "logging.")):
        return ["backend"]
    return ["frontend", "backend"]


def _category(target: str) -> str:
    prefix = target.split(".", 1)[0]
    return {
        "request": "field_type",
        "response": "field_type",
        "pagination": "pagination",
        "permission": "permission",
        "delete": "history",
        "restore": "history",
        "filter": "field_type",
        "sort": "enum",
        "authentication_error": "error",
        "missing_item": "error",
        "forbidden_item": "error",
        "ordinary_user": "permission",
        "read": "history",
        "update": "history",
        "create": "history",
        "frontend": "scope",
    }.get(prefix, "scope")


def build_v2(source: Path) -> V2Dataset:
    if source.suffix == ".json":
        data = RequirementDataset.model_validate(read_json(source))
    else:
        data = parse_markdown(source)
    chains: dict[str, list[V2Step]] = {}
    for chain in data.chains[:2]:
        previous: dict[str, object] = {}
        steps: list[V2Step] = []
        for step in chain.steps:
            facts: list[ContractFact] = []
            for label in step.labels:
                inherited = label.sources != [f"requirement:{step.step_id}"]
                previous_value = previous.get(label.fact_id)
                changed = not inherited and (
                    label.fact_id not in previous or previous_value != label.value
                )
                change_type = "inherited" if inherited else ("modified" if not changed else "added")
                if changed and label.fact_id in previous:
                    change_type = "rolled_back" if "回退" in step.raw_requirement else "modified"
                fact = ContractFact(
                    fact_id=label.fact_id,
                    statement=f"{label.target} = {json.dumps(label.value, ensure_ascii=False)}",
                    operation=label.target.split(".", 1)[0],
                    state=f"after-{step.step_id}",
                    category=_category(label.target),
                    required_sides=_side_for(label.target),
                    coverage="derivable" if inherited else "must_be_explicit",
                    change_type=change_type,
                    source_kind="inherited" if inherited else "current_requirement",
                    previous_value=previous_value,
                    target_value=label.value,
                    sources=label.sources,
                )
                facts.append(fact)
                previous[label.fact_id] = label.value
            steps.append(
                V2Step(
                    step_id=step.step_id,
                    raw_requirement=step.raw_requirement,
                    preserved_constraints=step.preserved_constraints,
                    required_sides=step.required_sides,
                    change_facts=[f for f in facts if f.change_type != "inherited"],
                    active_contract_facts=facts,
                )
            )
        chains[chain.chain_id] = steps
    return V2Dataset(
        schema_version="requirement-contract-v2",
        dataset_id="monoplanner-contract-v2-pilot",
        source_dataset=data.dataset_id,
        chains=chains,
    )


def build_answers(data: V2Dataset) -> V2Answers:
    return V2Answers(
        schema_version="requirement-contract-answers-v2",
        dataset_id=data.dataset_id,
        steps={
            step.step_id: [
                AnswerFact(
                    fact_id=fact.fact_id,
                    expected_value=fact.target_value,
                    required_sides=fact.required_sides,
                    coverage=fact.coverage,
                    sources=fact.sources,
                )
                for fact in step.active_contract_facts
            ]
            for values in data.chains.values()
            for step in values
        },
    )


def calibration_examples() -> dict:
    variants = {
        "consistent": (
            "must_be_explicit",
            "[FACT:page-min] Send page >= 1.",
            "[FACT:page-min] Validate page >= 1.",
            "Both required sides state the target fact.",
        ),
        "contradiction": (
            "must_be_explicit",
            "[FACT:page-min] Send page >= 1.",
            "[FACT:page-min] Accept page >= 0.",
            "The two sides require mutually exclusive minimum values.",
        ),
        "omission": (
            "must_be_explicit",
            "[FACT:page-min] Send page >= 1.",
            "Implement pagination validation.",
            "The backend omits a must-be-explicit fact.",
        ),
        "common_error": (
            "must_be_explicit",
            "[FACT:page-min] Send page >= 0.",
            "[FACT:page-min] Validate page >= 0.",
            "Both sides agree with each other but violate the target value 1.",
        ),
        "derivable": (
            "derivable",
            "Implement the current page contract.",
            "Preserve the current page contract.",
            "This inherited fact is context and need not be repeated explicitly.",
        ),
    }
    examples = []
    for label, (coverage, frontend, backend, rationale) in variants.items():
        for index in range(1, 6):
            examples.append(
                {
                    "example_id": f"{label}-{index}",
                    "fact": {
                        "fact_id": "page-min",
                        "statement": "page minimum is 1",
                        "target_value": 1,
                        "required_sides": ["frontend", "backend"],
                        "coverage": coverage,
                    },
                    "frontend_prompt": frontend,
                    "backend_prompt": backend,
                    "expected_label": label,
                    "rationale": rationale,
                    "status": "calibration_only_not_model_effectiveness",
                }
            )
    return {"schema_version": "review-calibration-v2", "examples": examples}


def _message(step: V2Step) -> str:
    return "\n\n".join(
        (
            "需求：" + step.raw_requirement,
            "持续有效约束：" + step.preserved_constraints,
            "本次变更事实：\n"
            + "\n".join(f"[FACT:{f.fact_id}] {f.statement}" for f in step.change_facts),
            "当前契约事实：\n"
            + "\n".join(
                f"[FACT:{f.fact_id}] ({','.join(f.required_sides)}; {f.coverage}) {f.statement}"
                for f in step.active_contract_facts
            ),
        )
    )


def _v2_rule_pack(step: V2Step) -> RequirementPack:
    sections = {}
    for side in ("frontend", "backend"):
        applicable = [f for f in step.active_contract_facts if side in f.required_sides]
        explicit = [f for f in applicable if f.coverage == "must_be_explicit"]
        prompt = "\n".join(
            [
                f"Implement {side} responsibilities. Preserve all unchanged constraints.",
                "Explicit contract checklist:",
                *[f"[FACT:{f.fact_id}] {f.statement}" for f in explicit],
                "Derivable inherited context:",
                *[f"[FACT:{f.fact_id}] {f.statement}" for f in applicable if f not in explicit],
            ]
        )
        sections[side] = {"needed": side in step.required_sides, "prompt": prompt}
    return RequirementPack.model_validate(sections)


def _v2_joint_pack(step: V2Step, generator: RecordedGenerator) -> RequirementPack:
    return RequirementPack(
        **generator(
            "Generate synchronized frontend and backend implementation instructions. "
            "Use the supplied current contract facts as the authoritative target. "
            "For every fact with coverage must_be_explicit, copy the complete supplied line, "
            "including its exact [FACT:id] marker, statement, and concrete value, into every "
            "applicable side prompt. A marker without the statement and value is an omission. "
            "Do not replace values with placeholders, add unresolved facts, or alter values. "
            "Do not add optional implementation advice that is not entailed by the contract. "
            "Only recommend platform validation primitives when their counting, null, default, "
            "and boundary semantics are exactly equivalent to the stated contract; otherwise "
            "use explicit application validation and omit the incompatible primitive.",
            _message(step),
            response_model=RequirementPack,
            task_key="prompt_pack",
        )
    )


def run(dataset_path: Path, output: Path, workers: int = 4) -> None:
    data = V2Dataset.model_validate(read_json(dataset_path))
    steps = [step for values in data.chains.values() for step in values]
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "dataset.json", data.model_dump(mode="json"))
    write_new(
        output / "manifest.json",
        {
            "protocol": "requirement-contract-v2-pilot",
            "created_at": now(),
            "methods": ["rule", "joint"],
            "repeats": 1,
            "workers": workers,
            "model_config": public_config("prompt_pack"),
        },
    )

    def execute(item: tuple[V2Step, str]):
        step, method = item
        unit = f"{step.step_id}-{method}-r1"
        directory = output / "units" / unit
        write_new(directory / "input.json", step.model_dump(mode="json"))
        generator = RecordedGenerator(directory / "calls")
        try:
            pack = _v2_rule_pack(step) if method == "rule" else _v2_joint_pack(step, generator)
            write_new(directory / "pack.json", pack.model_dump())
            write_new(directory / "outcome.json", {"status": "completed", "calls": generator.calls})
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
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(execute, (step, method)) for step in steps for method in ("rule", "joint")
        ]
        for future in as_completed(futures):
            summary[future.result()] += 1
    write_new(output / "completed.json", {"completed_at": now(), **summary})


def export_reviews(run_path: Path, output: Path) -> dict:
    dataset = V2Dataset.model_validate(read_json(run_path / "dataset.json"))
    steps = {step.step_id: step for values in dataset.chains.values() for step in values}
    packets = []
    mapping = {}
    reviews = []
    pack_paths = sorted((run_path / "units").glob("*/pack.json"))
    random.Random(20261003).shuffle(pack_paths)
    for index, pack_path in enumerate(pack_paths, 1):
        unit = pack_path.parent.name
        step_id, method = re.fullmatch(r"(.+)-(rule|joint)-r1", unit).groups()
        step = steps[step_id]
        pack = RequirementPack.model_validate(read_json(pack_path))
        blind_id = f"packet-{index:03d}"
        facts = [
            fact.model_dump(mode="json")
            for fact in step.active_contract_facts
            if fact.coverage == "must_be_explicit"
        ]
        packets.append(
            {
                "blind_id": blind_id,
                "pack_sha256": digest(pack.model_dump()),
                "raw_requirement": step.raw_requirement,
                "facts": facts,
                "frontend_prompt": pack.frontend.prompt,
                "backend_prompt": pack.backend.prompt,
            }
        )
        mapping[blind_id] = {"unit_id": unit, "method": method}
        reviews.append(
            {
                "blind_id": blind_id,
                "pack_sha256": digest(pack.model_dump()),
                "assessments": [
                    {"fact_id": fact["fact_id"], "label": "", "explanation": "", "evidence": []}
                    for fact in facts
                ],
            }
        )
    output.mkdir(parents=True, exist_ok=False)
    write_new(
        output / "packets.json",
        {"schema_version": "requirement-review-packets-v2", "packets": packets},
    )
    write_new(
        output / "blind-key.json",
        {"schema_version": "requirement-blind-key-v2", "mapping": mapping},
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
    return {"packets": len(packets), "assessments": sum(len(r["assessments"]) for r in reviews)}


def _semantic(pack: RequirementPack, step: V2Step, review: PackReview) -> dict:
    expected = {
        fact.fact_id: fact
        for fact in step.active_contract_facts
        if fact.coverage == "must_be_explicit"
    }
    assessments = {item.fact_id: item for item in review.assessments}
    if set(assessments) != set(expected) or len(assessments) != len(review.assessments):
        raise ValueError("Review must assess each must-be-explicit fact exactly once")
    if review.pack_sha256 != digest(pack.model_dump()):
        raise ValueError("Review pack hash mismatch")
    counts = Counter()
    for assessment in review.assessments:
        fact = expected[assessment.fact_id]
        sides = set()
        for evidence in assessment.evidence:
            text = getattr(pack, evidence.side).prompt
            if text[evidence.start : evidence.end] != evidence.quote:
                raise ValueError("Evidence offsets do not match prompt text")
            sides.add(evidence.side)
        if assessment.label == "consistent" and not set(fact.required_sides) <= sides:
            raise ValueError("Consistent facts need evidence from every required side")
        if assessment.label in {"contradiction", "common_error"} and sides != {
            "frontend",
            "backend",
        }:
            raise ValueError("Cross-side findings need evidence from both sides")
        counts[assessment.label] += 1
    evaluable = counts["omission"] == counts["uncertain"] == 0
    return {
        "status": "evaluated" if evaluable else "not_evaluable",
        "C_evaluable": counts["contradiction"] if evaluable else None,
        "C_observed": counts["contradiction"],
        "strict_success": evaluable and counts["contradiction"] == counts["common_error"] == 0,
        "label_counts": dict(counts),
    }


def report(run_path: Path, output: Path, reviews_path: Path | None = None) -> dict:
    dataset = V2Dataset.model_validate(read_json(run_path / "dataset.json"))
    steps = {step.step_id: step for values in dataset.chains.values() for step in values}
    reviews = {}
    reviewer = None
    if reviews_path:
        from evals.requirement_eval import ReviewFile

        review_file = ReviewFile.model_validate(read_json(reviews_path))
        reviewer = review_file.reviewer
        key = read_json(run_path / "review" / "blind-key.json")["mapping"]
        reviews = {key[item.blind_id]["unit_id"]: item for item in review_file.reviews}
    rows = []
    for outcome_path in sorted((run_path / "units").glob("*/outcome.json")):
        directory = outcome_path.parent
        unit = directory.name
        match = re.fullmatch(r"(.+)-(rule|joint)-r1", unit)
        step_id, method = match.groups()
        step = steps[step_id]
        outcome = read_json(outcome_path)
        coverage = {
            "must_be_explicit": 0,
            "marker_covered": 0,
            "statement_covered": 0,
            "derivable": 0,
        }
        issues = []
        if (directory / "pack.json").exists():
            pack = RequirementPack.model_validate(read_json(directory / "pack.json"))
            for fact in step.active_contract_facts:
                if fact.coverage == "must_be_explicit":
                    coverage["must_be_explicit"] += len(fact.required_sides)
                    coverage["marker_covered"] += sum(
                        f"[FACT:{fact.fact_id}]" in getattr(pack, side).prompt
                        for side in fact.required_sides
                    )
                    coverage["statement_covered"] += sum(
                        fact.statement in getattr(pack, side).prompt for side in fact.required_sides
                    )
                else:
                    coverage["derivable"] += 1
        else:
            issues.append("missing_pack")
        row = {
            "unit_id": unit,
            "step_id": step_id,
            "method": method,
            "status": outcome["status"],
            "calls": outcome.get("calls", 0),
            "coverage": coverage,
            "structural_issues": issues,
        }
        if unit in reviews and (directory / "pack.json").exists():
            row["semantic"] = _semantic(pack, step, reviews[unit])
        else:
            row["semantic"] = {"status": "pending_review"}
        rows.append(row)
    explicit_total = sum(row["coverage"]["must_be_explicit"] for row in rows)
    marker_covered = sum(row["coverage"]["marker_covered"] for row in rows)
    statement_covered = sum(row["coverage"]["statement_covered"] for row in rows)
    reviewed = [row["semantic"] for row in rows if row["semantic"]["status"] != "pending_review"]
    labels = sum((Counter(item.get("label_counts", {})) for item in reviewed), Counter())
    assessed = sum(labels.values())
    result = {
        "protocol": "requirement-contract-v2-pilot",
        "planned_units": len(steps) * 2,
        "completed_units": sum(row["status"] == "completed" for row in rows),
        "failed_units": sum(row["status"] != "completed" for row in rows),
        "total_model_calls": sum(row["calls"] for row in rows),
        "structural_valid_rate": sum(not row["structural_issues"] for row in rows) / len(rows),
        "marker_coverage_rate": marker_covered / explicit_total if explicit_total else None,
        "exact_statement_coverage_rate": (
            statement_covered / explicit_total if explicit_total else None
        ),
        "rows": rows,
        "semantic_metrics": {
            "C_evaluable": sum(
                item["C_evaluable"] for item in reviewed if item["status"] == "evaluated"
            )
            if reviewed
            else None,
            "C_observed": sum(item["C_observed"] for item in reviewed) if reviewed else None,
            "evaluable_rate": sum(item["status"] == "evaluated" for item in reviewed) / len(rows)
            if reviewed
            else None,
            "strict_success_rate": sum(item.get("strict_success", False) for item in reviewed)
            / len(rows)
            if reviewed
            else None,
            "label_counts": dict(labels),
            "explicit_semantic_coverage_rate": (
                (labels["consistent"] + labels["contradiction"] + labels["common_error"]) / assessed
                if assessed
                else None
            ),
            "omission_rate": labels["omission"] / assessed if assessed else None,
            "uncertain_rate": labels["uncertain"] / assessed if assessed else None,
            "common_error_rate": labels["common_error"] / assessed if assessed else None,
            "status": "complete" if len(reviewed) == len(rows) else "requires_blind_review",
        },
        "reviewer": reviewer,
    }
    by_method = {}
    for method in ("rule", "joint"):
        method_rows = [row for row in rows if row["method"] == method]
        method_reviewed = [
            row["semantic"] for row in method_rows if row["semantic"]["status"] != "pending_review"
        ]
        method_labels = sum(
            (Counter(item.get("label_counts", {})) for item in method_reviewed), Counter()
        )
        required = sum(row["coverage"]["must_be_explicit"] for row in method_rows)
        marker_covered = sum(row["coverage"]["marker_covered"] for row in method_rows)
        statement_covered = sum(row["coverage"]["statement_covered"] for row in method_rows)
        by_method[method] = {
            "planned_units": len(method_rows),
            "completed_units": sum(row["status"] == "completed" for row in method_rows),
            "marker_coverage_rate": marker_covered / required if required else None,
            "exact_statement_coverage_rate": (statement_covered / required if required else None),
            "explicit_semantic_coverage_rate": (
                (
                    method_labels["consistent"]
                    + method_labels["contradiction"]
                    + method_labels["common_error"]
                )
                / sum(method_labels.values())
                if method_labels
                else None
            ),
            "evaluable_units": sum(item["status"] == "evaluated" for item in method_reviewed),
            "strict_success_units": sum(
                item.get("strict_success", False) for item in method_reviewed
            ),
            "C_evaluable": sum(
                item["C_evaluable"] for item in method_reviewed if item["status"] == "evaluated"
            )
            if method_reviewed
            else None,
            "C_observed": sum(item["C_observed"] for item in method_reviewed)
            if method_reviewed
            else None,
            "label_counts": dict(method_labels),
        }
    result["method_summary"] = by_method
    pairs = {
        step.step_id: {row["method"]: row for row in rows if row["step_id"] == step.step_id}
        for values in dataset.chains.values()
        for step in values
    }
    result["paired_rule_vs_joint"] = {
        "pairs": len(pairs),
        "joint_minus_rule_marker_covered": sum(
            pair["joint"]["coverage"]["marker_covered"] - pair["rule"]["coverage"]["marker_covered"]
            for pair in pairs.values()
        ),
        "joint_minus_rule_statement_covered": sum(
            pair["joint"]["coverage"]["statement_covered"]
            - pair["rule"]["coverage"]["statement_covered"]
            for pair in pairs.values()
        ),
        "joint_strict_wins": sum(
            pair["joint"]["semantic"].get("strict_success", False)
            and not pair["rule"]["semantic"].get("strict_success", False)
            for pair in pairs.values()
        ),
        "rule_strict_wins": sum(
            pair["rule"]["semantic"].get("strict_success", False)
            and not pair["joint"]["semantic"].get("strict_success", False)
            for pair in pairs.values()
        ),
    }
    write_new(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-data")
    build.add_argument("source", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--answers", type=Path)
    build.add_argument("--calibration", type=Path)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("dataset", type=Path)
    run_parser.add_argument("output", type=Path)
    run_parser.add_argument("--workers", type=int, default=4)
    report_parser = sub.add_parser("report")
    report_parser.add_argument("run", type=Path)
    report_parser.add_argument("output", type=Path)
    report_parser.add_argument("--reviews", type=Path)
    review_parser = sub.add_parser("review-export")
    review_parser.add_argument("run", type=Path)
    review_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "build-data":
        data = build_v2(args.source)
        write_new(args.output, data.model_dump(mode="json"))
        if args.answers:
            write_new(args.answers, build_answers(data).model_dump(mode="json"))
        if args.calibration:
            write_new(args.calibration, calibration_examples())
    elif args.command == "run":
        run(args.dataset, args.output, args.workers)
    elif args.command == "review-export":
        print(json.dumps(export_reviews(args.run, args.output), ensure_ascii=False))
    else:
        print(json.dumps(report(args.run, args.output, args.reviews), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
