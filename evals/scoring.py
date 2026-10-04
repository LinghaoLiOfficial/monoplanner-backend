"""Evidence validation and counting; human judgments are not replaced by model opinions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from evals.dataset import Answer, StrictModel
from evals.storage import digest

LABELS = ("consistent", "contradiction", "omission", "uncertain", "common_error")


class Evidence(StrictModel):
    side: Literal["frontend", "backend"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class Assessment(StrictModel):
    fact_id: str
    label: Literal["consistent", "contradiction", "omission", "uncertain", "common_error"]
    explanation: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)


class Review(StrictModel):
    status: Literal["pending", "reviewed"] = "pending"
    reviewer: str = ""
    human_attestation: bool = False
    pack_sha256: str
    assessments: list[Assessment] = Field(default_factory=list)


def structural_issues(pack: dict[str, Any], answer: Answer) -> list[str]:
    issues = []
    if not isinstance(pack, dict):
        return ["invalid_pack"]
    for side in ("frontend", "backend"):
        section = pack.get(f"{side}_prompt")
        if not isinstance(section, dict):
            issues.append(f"missing_section:{side}")
            continue
        required = side in answer.required_sides
        if section.get("needed") is not required:
            issues.append(f"scope_mismatch:{side}")
        if not isinstance(section.get("prompt"), str):
            issues.append(f"invalid_prompt_type:{side}")
        elif required and not section["prompt"].strip():
            issues.append(f"empty_prompt:{side}")
    return issues


def score(
    pack: dict[str, Any] | None,
    answer: Answer,
    review: Review | None,
    generation_status: str = "completed",
) -> dict[str, Any]:
    base = {
        "C": None,
        "observed_contradictions": 0,
        "valid_zero": False,
        "common_errors": 0,
        "label_counts": {label: 0 for label in LABELS},
    }
    if generation_status != "completed" or pack is None:
        return {**base, "status": generation_status, "issues": ["no_completed_pack"]}
    issues = structural_issues(pack, answer)
    if issues:
        return {**base, "status": "invalid_pack", "issues": issues}
    if review is None or review.status != "reviewed":
        return {**base, "status": "pending_review", "issues": []}
    if review.pack_sha256 != digest(pack):
        raise ValueError("Review does not match pack hash")
    if not review.reviewer.strip() or not review.human_attestation:
        raise ValueError("Final review requires a named human and attestation")
    expected = {fact.fact_id: fact for fact in answer.facts}
    assessed: dict[str, Assessment] = {}
    for assessment in review.assessments:
        fact = expected.get(assessment.fact_id)
        if fact is None and not assessment.fact_id.startswith("extra:"):
            raise ValueError(f"Unknown fact ID: {assessment.fact_id}")
        if fact is None and assessment.label != "contradiction":
            raise ValueError("Extra facts may only add evidenced contradictions")
        previous = assessed.get(assessment.fact_id)
        if previous and previous.label != assessment.label:
            raise ValueError("Conflicting labels for the same atomic fact")
        seen_sides = set()
        for evidence in assessment.evidence:
            text = pack[f"{evidence.side}_prompt"]["prompt"]
            if (
                evidence.end <= evidence.start
                or text[evidence.start : evidence.end] != evidence.quote
            ):
                raise ValueError("Evidence quote must match exact character offsets in its prompt")
            seen_sides.add(evidence.side)
        if assessment.label in {"contradiction", "common_error"}:
            if seen_sides != {"frontend", "backend"}:
                raise ValueError(
                    "A cross-side conflict/error needs both frontend and backend evidence"
                )
        if assessment.label == "consistent" and fact:
            if not set(fact.required_sides) <= seen_sides:
                raise ValueError("Consistency needs evidence for every required side")
        assessed[assessment.fact_id] = assessment
    missing = set(expected) - set(assessed)
    if missing:
        raise ValueError(f"Review omitted required facts: {sorted(missing)}")
    counts = {label: sum(a.label == label for a in assessed.values()) for label in LABELS}
    valid = counts["omission"] == counts["uncertain"] == 0
    return {
        "C": counts["contradiction"] if valid else None,
        "observed_contradictions": counts["contradiction"],
        "valid_zero": valid and counts["contradiction"] == counts["common_error"] == 0,
        "common_errors": counts["common_error"],
        "label_counts": counts,
        "status": "evaluated" if valid else "not_evaluable",
        "issues": [k for k in ("omission", "uncertain") if counts[k]],
    }
