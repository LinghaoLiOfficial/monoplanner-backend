import json
from pathlib import Path

from evals.requirement_eval_v2 import V2Answers, V2Dataset, _v2_rule_pack


def load_data() -> V2Dataset:
    return V2Dataset.model_validate(
        json.loads(Path("data/inputs/monoplanner-contract-v2-pilot.json").read_text())
    )


def test_v2_development_dataset_has_six_continuous_steps() -> None:
    data = load_data()
    assert list(data.chains) == ["chain-01", "chain-02"]
    assert sum(len(steps) for steps in data.chains.values()) == 6
    assert (
        sum(len(step.active_contract_facts) for steps in data.chains.values() for step in steps)
        == 73
    )
    assert sum(len(step.change_facts) for steps in data.chains.values() for step in steps) == 41


def test_answers_match_v2_facts_without_generation_fields() -> None:
    data = load_data()
    answers = V2Answers.model_validate(
        json.loads(Path("data/answers/monoplanner-contract-v2-pilot.json").read_text())
    )
    assert answers.dataset_id == data.dataset_id
    assert set(answers.steps) == {step.step_id for steps in data.chains.values() for step in steps}


def test_rule_pack_marks_only_explicit_applicable_facts_as_required() -> None:
    step = load_data().chains["chain-01"][1]
    pack = _v2_rule_pack(step)
    assert "[FACT:request-title-max-length]" in pack.frontend.prompt
    assert "[FACT:request-title-max-length]" in pack.backend.prompt
    assert "[FACT:request-title-trim]" in pack.frontend.prompt
    assert (
        next(
            fact for fact in step.active_contract_facts if fact.fact_id == "request-title-trim"
        ).coverage
        == "derivable"
    )


def test_calibration_contains_five_examples_per_class() -> None:
    calibration = json.loads(Path("data/calibration/requirement-review-v2.json").read_text())
    counts = {}
    for example in calibration["examples"]:
        counts[example["expected_label"]] = counts.get(example["expected_label"], 0) + 1
    assert counts == {
        "consistent": 5,
        "contradiction": 5,
        "omission": 5,
        "common_error": 5,
        "derivable": 5,
    }
