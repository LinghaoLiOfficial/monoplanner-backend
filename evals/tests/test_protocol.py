"""Synthetic software fixtures, never the human benchmark or model-effect results."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from evals.dataset import TOPICS, Answer, Dataset, PackInput, freeze, validate_pair
from evals.fullchain import safe_database
from evals.methods import independent_pack, joint_pack, rule_pack
from evals.reports import export_reviews, report, summarize
from evals.runner import run
from evals.scoring import Assessment, Evidence, Review, score
from evals.storage import digest, read_json, write_new


def answer(category="field_type", sides=None):
    sides = sides or ["frontend", "backend"]
    return Answer(
        required_sides=sides,
        facts=[
            {
                "fact_id": "f1",
                "statement": "Use the target contract",
                "operation": "update",
                "state": "after",
                "category": category,
                "required_sides": sides,
                "sources": ["requirement:c01-s1"],
            }
        ],
    )


def pack(front="title is string", back="title is integer", sides=None):
    sides = sides or ["frontend", "backend"]
    return {
        f"{side}_prompt": {"needed": side in sides, "prompt": text}
        for side, text in (("frontend", front), ("backend", back))
    }


def review(value, label="contradiction", sides=None):
    sides = sides or ["frontend", "backend"]
    evidence = [
        Evidence(
            side=s,
            start=0,
            end=len(value[f"{s}_prompt"]["prompt"]),
            quote=value[f"{s}_prompt"]["prompt"],
        )
        for s in sides
    ]
    return Review(
        status="reviewed",
        reviewer="software-test-fixture",
        human_attestation=True,
        pack_sha256=digest(value),
        assessments=[
            Assessment(
                fact_id="f1", label=label, explanation="Fixture assertion", evidence=evidence
            )
        ],
    )


@pytest.mark.parametrize(
    "category,front,back",
    [
        ("field_type", "title is string", "title is integer"),
        ("path_method", "PATCH /items/{id}", "PUT /items/{id}"),
        ("permission", "all users may delete", "only owner may delete"),
        ("pagination", "page starts at 1", "page starts at 0"),
        ("required_nullable", "null clears description", "null is forbidden"),
        ("enum", "status: active, paused", "status: active, disabled"),
        ("error", "missing item returns 404", "missing item returns 400"),
        ("history", "restore title max length 100", "retain title max length 50"),
    ],
)
def test_evidenced_conflict_categories(category, front, back):
    value = pack(front, back)
    assert score(value, answer(category), review(value))["C"] == 1


def test_synonyms_and_duplicate_fact_count():
    value = pack("title is a string", "title is text")
    assert score(value, answer(), review(value, "consistent"))["valid_zero"]
    human = review(value)
    human.assessments.append(human.assessments[0])
    assert score(value, answer(), human)["C"] == 1


@pytest.mark.parametrize("label", ["omission", "uncertain"])
def test_missing_and_ambiguous_not_zero(label):
    value = pack()
    result = score(value, answer(), review(value, label))
    assert result["C"] is None and not result["valid_zero"]


def test_common_error_is_not_success():
    value = pack("title is integer", "title is integer")
    result = score(value, answer(), review(value, "common_error"))
    assert result["C"] == 0 and result["common_errors"] == 1
    assert not result["valid_zero"]


def test_single_side_and_empty_pack():
    value = pack("change label only", "unchanged", ["frontend"])
    assert score(value, answer(sides=["frontend"]), review(value, "consistent", ["frontend"]))[
        "valid_zero"
    ]
    assert score({}, answer(), None)["C"] is None
    value["frontend_prompt"]["prompt"] = []
    assert score(value, answer(), None)["status"] == "invalid_pack"


def test_evidence_and_attestation_required():
    value = pack()
    for mutation in ("quote", "one_side", "human", "missing_fact"):
        human = review(value)
        if mutation == "quote":
            human.assessments[0].evidence[0].quote = "invented"
        elif mutation == "one_side":
            human.assessments[0].evidence.pop()
        elif mutation == "human":
            human.human_attestation = False
        else:
            human.assessments.clear()
        with pytest.raises(ValueError):
            score(value, answer(), human)


def dataset_fixture(tmp_path):
    chains = []
    gold = {}
    for i, topic in enumerate(TOPICS, 1):
        initial = {"api_contract": {"version": 1, "content": {"title": "string"}}}
        previous = initial
        steps = []
        for j in range(1, 4):
            step_id = f"c{i:02d}-s{j}"
            target = {"api_contract": {"version": j + 1, "content": {"title": "string"}}}
            steps.append(
                {
                    "step_id": step_id,
                    "raw_requirement": "Synthetic fixture change",
                    "preserved_constraints": ["title is string"],
                    "sources": [f"requirement:{step_id}"],
                    "pack_input": {
                        "project_config": {},
                        "selected_story": {"implementation_scope": "fullstack"},
                        "change_sets": [{"change": "synthetic"}],
                        "old_versions": previous,
                        "new_versions": target,
                    },
                }
            )
            gold[step_id] = answer().model_dump()
            gold[step_id]["facts"][0]["sources"] = [f"requirement:{step_id}"]
            previous = target
        chains.append(
            {
                "chain_id": f"chain-{i:02d}",
                "topic": topic,
                "split": "dev" if i <= 2 else "test",
                "author": "fixture-not-human-data",
                "provenance": "human_handwritten",
                "handwritten_attestation": True,
                "initial_assets": initial,
                "steps": steps,
            }
        )
    inputs = tmp_path / "inputs.json"
    answers = tmp_path / "answers.json"
    write_new(
        inputs,
        {
            "dataset_id": "synthetic-software-fixture",
            "status": "ready",
            "source_commit": "1762adac607a1b29cfc4da129557780beea71616",
            "chains": chains,
        },
    )
    write_new(
        answers,
        {
            "dataset_id": "synthetic-software-fixture",
            "author": "fixture",
            "frozen_before_outputs_attestation": True,
            "steps": gold,
        },
    )
    return inputs, answers


def test_draft_rejected_and_continuity(tmp_path):
    with pytest.raises(ValidationError):
        Dataset.model_validate(read_json(Path("data/inputs/benchmark.json")))
    inputs, answers = dataset_fixture(tmp_path)
    validate_pair(inputs, answers)
    raw = read_json(inputs)
    raw["chains"][0]["steps"][1]["pack_input"]["old_versions"] = {}
    with pytest.raises(ValidationError):
        Dataset.model_validate(raw)


def test_offline_end_to_end_preserves_denominator(tmp_path, monkeypatch):
    inputs, answers = dataset_fixture(tmp_path)
    lock = tmp_path / "freeze.json"
    freeze(inputs, answers, lock, "pilot")
    output = tmp_path / "run"
    run(inputs, lock, output, "dev", ["rule"], 1)
    manifest = read_json(output / "manifest.json")
    assert len(manifest["planned"]) == 6
    export_reviews(output, answers, tmp_path / "review")
    result = report(output, answers, tmp_path / "review/reviews.json", tmp_path / "report")
    assert result["overall"]["planned"] == 6
    assert result["overall"]["statuses"] == {"pending_review": 6}
    assert result["api_call_count"] == 0
    replay = report(output, answers, tmp_path / "review/reviews.json", tmp_path / "replay")
    assert replay["units"] == result["units"]
    with pytest.raises(FileExistsError):
        run(inputs, lock, output, "dev", ["rule"], 1)
    with pytest.raises(ValueError, match="Formal freeze"):
        freeze(inputs, answers, tmp_path / "formal.json", "formal")


def test_failure_does_not_disappear():
    rows = [
        score(None, answer(), None, "generation_failed"),
        score(pack(), answer(), review(pack(), "consistent")),
    ]
    assert summarize(rows)["valid_zero_rate"] == 0.5


def test_generation_never_opens_answers(tmp_path, monkeypatch):
    inputs, answers = dataset_fixture(tmp_path)
    lock = tmp_path / "freeze.json"
    freeze(inputs, answers, lock, "pilot")
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        if path == answers:
            raise AssertionError("Answer leakage")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    run(inputs, lock, tmp_path / "run", "dev", ["rule"], 1)


def test_independent_arms_and_joint_cache_isolation():
    value = PackInput(
        project_config={},
        selected_story={"implementation_scope": "fullstack"},
        change_sets=[{"id": "change"}],
        old_versions={"old": {}},
        new_versions={"new": {}},
    )
    calls = []

    def fake(system, user, **kwargs):
        calls.append((system, user))
        return {
            "needed": True,
            "title": "fixture",
            "prompt": "OUTPUT_SENTINEL",
            "affected_files": [],
            "do_not_modify": [],
            "verification_steps": [],
        }

    independent_pack(value, fake)
    assert len(calls) == 2 and calls[0][1] == calls[1][1]
    assert all("OUTPUT_SENTINEL" not in user for _, user in calls)
    count = []

    def joint_fake(system, user, **kwargs):
        count.append(user)
        output = rule_pack(value)
        output["execution_order"] = ["backend_prompt", "frontend_prompt"]
        return output

    joint_pack(value, joint_fake)
    joint_pack(value, joint_fake)
    assert len(count) == 2


@pytest.mark.parametrize(
    "url", ["sqlite:///test_eval", "postgresql://localhost/app", "postgresql://localhost/prod"]
)
def test_database_guard(url):
    with pytest.raises(ValueError):
        safe_database(url)


def test_bounded_recorded_calls(tmp_path, monkeypatch):
    from app.llm.client import OpenAICompatibleLLMClient
    from app.llm.task_config import LLMTaskConfig
    from evals import transport

    class Output(BaseModel):
        title: str

    config = LLMTaskConfig(
        model="openai/gpt-5-mini",
        temperature=0.2,
        structured_max_retries=2,
        base_url="https://example.invalid/v1",
        api_key="SECRET",
    )
    monkeypatch.setattr(transport, "get_llm_task_config", lambda _: config)
    monkeypatch.setattr(
        transport,
        "create_llm_client",
        lambda _: OpenAICompatibleLLMClient(
            base_url=config.base_url, api_key=config.api_key, model=config.model
        ),
    )
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 10}}
        )

    monkeypatch.setattr(transport.httpx, "post", post)
    generator = transport.RecordedGenerator(tmp_path)
    with pytest.raises(ValueError, match="retries exhausted"):
        generator("test SECRET", "input", response_model=Output, task_key="prompt_pack")
    assert generator.calls == len(calls) == 3
    assert len(list(tmp_path.glob("*.response.json"))) == 3
    assert "SECRET" not in "".join(p.read_text() for p in tmp_path.glob("*.json"))


def test_no_history_overwrite(tmp_path):
    path = tmp_path / "result.json"
    write_new(path, {"version": 1})
    with pytest.raises(FileExistsError):
        write_new(path, {"version": 2})
    assert json.loads(path.read_text())["version"] == 1
