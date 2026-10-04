"""Runner tests use mocks, not paid calls or real databases."""

import pytest

from evals import fullchain, runner
from evals.dataset import freeze, verify_lock
from evals.methods import rule_pack
from evals.storage import read_json, write_new
from evals.tests.test_protocol import dataset_fixture


def test_formal_schedule_and_fullchain_upstream_failure(tmp_path, monkeypatch):
    inputs, answers = dataset_fixture(tmp_path)
    pilot_lock = tmp_path / "pilot.json"
    freeze(inputs, answers, pilot_lock, "pilot")
    lock = read_json(pilot_lock)
    # Inject a formal lock ONLY in this isolated test, never in the benchmark.
    lock["stage"] = "formal"
    config = dict(
        lock["model_configs"]["prompt_pack"],
        model="openai/gpt-5-mini",
        temperature=0.2,
        structured_max_retries=2,
    )
    lock["model_configs"] = {task: {**config, "task_key": task} for task in lock["model_configs"]}
    formal_lock = tmp_path / "formal.json"
    write_new(formal_lock, lock)
    monkeypatch.setattr(runner, "public_config", lambda task: {**config, "task_key": task})
    monkeypatch.setattr(fullchain, "safe_database", lambda _: None)
    monkeypatch.setattr(runner, "joint_pack", lambda value, _: rule_pack(value))
    monkeypatch.setattr(runner, "independent_pack", lambda value, _: rule_pack(value))
    instances = []

    class FailedChain:
        def __init__(self, url, chain, audit):
            self.chain_id = chain.chain_id
            self.calls = 0
            self.closed = False
            instances.append(self)

        def step(self, step, generator, directory):
            self.calls += 1
            raise ValueError("Synthetic upstream failure")

        def close(self):
            self.closed = True

    monkeypatch.setattr(fullchain, "FullChain", FailedChain)
    output = tmp_path / "run"
    runner.run(
        inputs, formal_lock, output, "test", list(runner.METHODS), 3, "postgresql://mock/mock_eval"
    )
    manifest = read_json(output / "manifest.json")
    assert len(manifest["planned"]) == 288
    assert len(instances) == 24
    assert all(instance.closed and instance.calls == 1 for instance in instances)
    statuses = [
        read_json(output / "units" / u["unit_id"] / "outcome.json")["status"]
        for u in manifest["planned"]
        if u["method"] == "fullchain"
    ]
    assert statuses.count("generation_failed") == 24
    assert statuses.count("blocked_upstream") == 48


def test_input_drift_and_formal_gate(tmp_path):
    inputs, answers = dataset_fixture(tmp_path)
    lock = tmp_path / "lock.json"
    freeze(inputs, answers, lock, "pilot")
    with pytest.raises(ValueError, match="formal freeze"):
        verify_lock(inputs, lock, "test")
    changed = read_json(inputs)
    changed["dataset_id"] = "changed-after-freeze"
    new_inputs = tmp_path / "changed.json"
    write_new(new_inputs, changed)
    with pytest.raises(ValueError, match="Inputs changed"):
        verify_lock(new_inputs, lock, "dev")


def test_config_drift_rejected_before_output_or_call(tmp_path, monkeypatch):
    inputs, answers = dataset_fixture(tmp_path)
    lock = tmp_path / "lock.json"
    freeze(inputs, answers, lock, "pilot")
    config = dict(
        read_json(lock)["model_configs"]["prompt_pack"], model="openai/gpt-5-mini", temperature=0.7
    )
    monkeypatch.setattr(runner, "public_config", lambda _: config)
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="configuration changed"):
        runner.run(inputs, lock, output, "dev", ["joint"], 1)
    assert not output.exists()
