import json
from pathlib import Path

import pytest

from evals.requirement_eval import (
    TOPICS,
    PackReview,
    RequirementDataset,
    RequirementPack,
    _score_review,
    export_reviews,
)
from evals.storage import digest


def test_received_markdown_is_complete_and_separates_labels() -> None:
    data = RequirementDataset.model_validate(
        json.loads(Path("data/inputs/monoplanner-new-data-v1.json").read_text())
    )
    assert tuple(chain.topic for chain in data.chains) == TOPICS
    assert sum(len(chain.steps) for chain in data.chains) == 30
    assert all(step.labels for chain in data.chains for step in chain.steps)
    assert {chain.split for chain in data.chains[:2]} == {"dev"}
    assert {chain.split for chain in data.chains[2:]} == {"test"}


def test_review_requires_both_sides_for_a_contradiction() -> None:
    data = RequirementDataset.model_validate(
        json.loads(Path("data/inputs/monoplanner-new-data-v1.json").read_text())
    )
    step = data.chains[0].steps[0]
    pack = RequirementPack.model_validate(
        {
            "frontend": {"needed": True, "prompt": "title must be text"},
            "backend": {"needed": True, "prompt": "title must be an integer"},
        }
    )
    review = {
        "blind_id": "packet-001",
        "pack_sha256": digest(pack.model_dump()),
        "assessments": [
            {
                "fact_id": label.fact_id,
                "label": "contradiction" if label == step.labels[0] else "omission",
                "explanation": "not assessed",
                "evidence": [{"side": "frontend", "start": 0, "end": 5, "quote": "title"}]
                if label == step.labels[0]
                else [],
            }
            for label in step.labels
        ],
    }
    with pytest.raises(ValueError, match="both-side"):
        _score_review(pack, step, PackReview.model_validate(review))


def test_export_hides_unit_id_from_packets(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    source = Path("data/inputs/monoplanner-new-data-v1.json")
    (run / "dataset.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    unit = run / "units" / "chain-01-c01-s1-rule-r1"
    unit.mkdir(parents=True)
    (unit / "input.json").write_text(
        json.dumps(
            {
                "step_id": "c01-s1",
                "raw_requirement": "x",
                "preserved_constraints": "y",
                "required_sides": ["frontend", "backend"],
            }
        ),
        encoding="utf-8",
    )
    (unit / "outcome.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    (unit / "pack.json").write_text(
        json.dumps(
            {
                "frontend": {"needed": True, "prompt": "x"},
                "backend": {"needed": True, "prompt": "y"},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "review"
    export_reviews(run, output)
    packets = (output / "packets.json").read_text(encoding="utf-8")
    assert "chain-01" not in packets
    assert "chain-01" in (output / "blind-key.json").read_text(encoding="utf-8")
