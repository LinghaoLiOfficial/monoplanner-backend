from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.storage import ROOT, code_hashes, digest, now, read_json, source_hashes, write_new

SIDES = ("frontend", "backend")
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
PIN = "1762adac607a1b29cfc4da129557780beea71616"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackInput(StrictModel):
    project_config: dict[str, Any]
    selected_story: dict[str, Any] | None
    change_sets: list[dict[str, Any]] = Field(min_length=1)
    old_versions: dict[str, Any] = Field(min_length=1)
    new_versions: dict[str, Any] = Field(min_length=1)


class Step(StrictModel):
    step_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    raw_requirement: str = Field(min_length=1)
    preserved_constraints: list[str]
    sources: list[str] = Field(min_length=1)
    pack_input: PackInput


class Chain(StrictModel):
    chain_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    topic: str
    split: Literal["dev", "test"]
    author: str = Field(min_length=1)
    provenance: Literal["human_handwritten"]
    handwritten_attestation: Literal[True]
    initial_assets: dict[str, Any] = Field(min_length=1)
    steps: list[Step] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def continuity(self) -> Chain:
        previous = self.initial_assets
        for step in self.steps:
            if step.pack_input.old_versions != previous:
                raise ValueError(f"{step.step_id}: old_versions must equal the previous state")
            previous = step.pack_input.new_versions
        return self


class Dataset(StrictModel):
    dataset_id: str
    status: Literal["ready"]
    source_commit: Literal["1762adac607a1b29cfc4da129557780beea71616"]
    chains: list[Chain] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def partition(self) -> Dataset:
        if sorted(c.topic for c in self.chains) != sorted(TOPICS):
            raise ValueError("The ten preregistered topics must each appear once")
        expected_dev = set(TOPICS[:2])
        for chain in self.chains:
            if (chain.split == "dev") != (chain.topic in expected_dev):
                raise ValueError("Only item_validation and pagination are development chains")
        ids = [s.step_id for c in self.chains for s in c.steps]
        if len(set(ids)) != len(ids) or len({c.chain_id for c in self.chains}) != 10:
            raise ValueError("Chain and step IDs must be unique")
        for chain in self.chains:
            for step in chain.steps:
                require_sources(step.sources, step.step_id)
        return self


class Fact(StrictModel):
    fact_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    state: str = Field(min_length=1)
    category: Literal[
        "path_method",
        "field_type",
        "required_nullable",
        "enum",
        "permission",
        "pagination",
        "error",
        "history",
        "scope",
    ]
    required_sides: list[Literal["frontend", "backend"]] = Field(min_length=1, max_length=2)
    sources: list[str] = Field(min_length=1)


class Answer(StrictModel):
    required_sides: list[Literal["frontend", "backend"]] = Field(max_length=2)
    facts: list[Fact] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_facts(self) -> Answer:
        ids = [f.fact_id for f in self.facts]
        if len(set(ids)) != len(ids) or len(set(self.required_sides)) != len(self.required_sides):
            raise ValueError("Duplicate facts or roles")
        for fact in self.facts:
            if len(set(fact.required_sides)) != len(fact.required_sides):
                raise ValueError("Duplicate fact roles")
            if not set(fact.required_sides) <= set(self.required_sides):
                raise ValueError("Fact refers to a side not required by this answer")
        return self


class Answers(StrictModel):
    dataset_id: str
    author: str = Field(min_length=1)
    frozen_before_outputs_attestation: Literal[True]
    steps: dict[str, Answer]


def require_sources(sources: list[str], step_id: str) -> None:
    prefix = f"https://github.com/fastapi/full-stack-fastapi-template/blob/{PIN}/"
    for source in sources:
        if not (source.startswith(prefix) or source == f"requirement:{step_id}"):
            raise ValueError(f"Unpinned or unsupported source: {source}")
        if source.startswith(prefix):
            relative = source.removeprefix(prefix).split("#", 1)[0]
            local = (ROOT / "data/sources" / relative).resolve()
            if not local.is_relative_to(ROOT / "data/sources") or not local.is_file():
                raise ValueError(f"Source has no checked-in offline copy: {source}")


def load_inputs(path: Path) -> Dataset:
    # Generation only loads this file; the answer file is not part of PackInput.
    return Dataset.model_validate(read_json(path))


def validate_pair(inputs: Path, answers: Path) -> tuple[Dataset, Answers]:
    data = load_inputs(inputs)
    gold = Answers.model_validate(read_json(answers))
    steps = {s.step_id for c in data.chains for s in c.steps}
    if gold.dataset_id != data.dataset_id or set(gold.steps) != steps:
        raise ValueError("Answers must match every input step, with no extras")
    for step_id, answer in gold.steps.items():
        for fact in answer.facts:
            require_sources(fact.sources, step_id)
    return data, gold


def freeze(
    inputs: Path, answers: Path, output: Path, stage: str, pilot_run: Path | None = None
) -> None:
    validate_pair(inputs, answers)
    if stage not in {"pilot", "formal"}:
        raise ValueError("Unknown freeze stage")
    pilot = None
    if stage == "formal":
        if pilot_run is None:
            raise ValueError("Formal freeze requires a completed, reviewed development pilot")
        manifest = read_json(pilot_run / "manifest.json")
        read_json(pilot_run / "completed.json")
        pilot = read_json(pilot_run / "pilot-report" / "report.json")
        if (
            manifest["split"] != "dev"
            or set(manifest["methods"]) != set(("rule", "independent", "joint", "fullchain"))
            or any(r["status"] == "pending_review" for r in pilot["units"])
        ):
            raise ValueError("Pilot must cover all four arms and review every completed pack")
    from evals.fullchain import RESPONSE_MODELS
    from evals.transport import public_config

    write_new(
        output,
        {
            "version": 1,
            "stage": stage,
            "created_at": now(),
            "input_sha256": digest(read_json(inputs)),
            "answer_sha256": digest(read_json(answers)),
            "code_hashes": code_hashes(),
            "source_hashes": source_hashes(),
            "model_configs": {task: public_config(task) for task in RESPONSE_MODELS},
            "pilot_report_sha256": digest(pilot) if pilot else None,
            "protocol": {"repeats": 3, "steps_per_chain": 3, "target": 0.9},
        },
    )


def verify_lock(inputs: Path, lock_path: Path, split: str) -> dict[str, Any]:
    lock = read_json(lock_path)
    if lock["input_sha256"] != digest(read_json(inputs)):
        raise ValueError("Inputs changed after freeze")
    if lock["code_hashes"] != code_hashes() or lock["source_hashes"] != source_hashes():
        raise ValueError("Code, rubric or sources changed after freeze")
    if split == "test" and lock["stage"] != "formal":
        raise ValueError("Test runs require a formal freeze after the development pilot")
    return lock


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9_-]+", value):
        raise ValueError("ID must contain only lowercase letters, digits, hyphens or underscores")
    return value
