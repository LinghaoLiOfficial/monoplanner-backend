from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from evals.dataset import load_inputs, safe_id, verify_lock
from evals.methods import independent_pack, joint_pack, rule_pack
from evals.storage import digest, git_revision, now, write_new
from evals.transport import RecordedGenerator, public_config

METHODS = ("rule", "independent", "joint", "fullchain")


def run(
    inputs: Path,
    lock_path: Path,
    output: Path,
    split: str,
    methods: list[str],
    repeats: int = 3,
    database_url: str | None = None,
) -> None:
    data = load_inputs(inputs)
    lock = verify_lock(inputs, lock_path, split)
    if not methods or len(set(methods)) != len(methods) or set(methods) - set(METHODS):
        raise ValueError("Choose distinct known methods")
    if repeats < 1 or repeats > 3 or (split == "test" and repeats != 3):
        raise ValueError("Formal runs require three repeats; pilots allow one to three")
    if split == "test" and set(methods) != set(METHODS):
        raise ValueError("Formal runs must include all four preregistered arms")
    if "fullchain" in methods:
        from evals.fullchain import safe_database

        if not database_url:
            raise ValueError("fullchain requires explicit EVAL_DATABASE_URL, never DATABASE_URL")
        safe_database(database_url)
    for method in methods:
        if method != "rule":
            config = public_config("prompt_pack")
            if config["model"] != "openai/gpt-5-mini":
                raise ValueError("Configure the preregistered openai/gpt-5-mini model")
    if set(methods) != {"rule"}:
        from evals.fullchain import RESPONSE_MODELS

        for task in RESPONSE_MODELS if "fullchain" in methods else ("prompt_pack",):
            config = public_config(task)
            if config != lock["model_configs"][task]:
                raise ValueError(f"{task}: effective configuration changed after freeze")
            if config["model"] != "openai/gpt-5-mini" or config["temperature"] != 0.2:
                raise ValueError(f"{task}: model/temperature differs from protocol")
            if config["structured_max_retries"] != 2:
                raise ValueError(f"{task}: protocol requires exactly two structured retries")
    chains = [c for c in data.chains if c.split == split]
    planned = [
        {
            "unit_id": safe_id(f"{c.chain_id}-{s.step_id}-{method}-r{r}"),
            "chain_id": c.chain_id,
            "step_id": s.step_id,
            "method": method,
            "repeat": r,
        }
        for c in chains
        for method in methods
        for r in range(1, repeats + 1)
        for s in c.steps
    ]
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "inputs.json", data.model_dump())
    write_new(output / "freeze.json", lock)
    write_new(
        output / "manifest.json",
        {
            "version": 1,
            "created_at": now(),
            "git_revision": git_revision(),
            "split": split,
            "dataset_id": data.dataset_id,
            "planned": planned,
            "methods": methods,
            "repeats": repeats,
            "config": public_config("prompt_pack") if set(methods) != {"rule"} else None,
            "no_cost_cap": True,
            "rule_repeats": "deterministic outputs; not independent samples",
        },
    )
    from evals.fullchain import FullChain

    for chain in chains:
        for method in methods:
            for repeat in range(1, repeats + 1):
                fullchain = None
                blocked = False
                try:
                    if method == "fullchain":
                        audit = output / f"{chain.chain_id}-fullchain-r{repeat}"
                        fullchain = FullChain(database_url, chain, audit)
                except Exception as exc:
                    blocked = True
                    write_new(
                        output / f"{chain.chain_id}-fullchain-r{repeat}" / "setup-error.json",
                        {"error_type": type(exc).__name__, "status": "setup_failed"},
                    )
                try:
                    for step in chain.steps:
                        unit_id = f"{chain.chain_id}-{step.step_id}-{method}-r{repeat}"
                        directory = output / "units" / unit_id
                        value = step.pack_input
                        write_new(
                            directory / "input.json",
                            {
                                "raw_requirement": step.raw_requirement,
                                "pack_input": value.model_dump() if method != "fullchain" else None,
                                "pack_input_sha256": digest(value.model_dump())
                                if method != "fullchain"
                                else None,
                            },
                        )
                        if blocked:
                            write_new(directory / "outcome.json", {"status": "blocked_upstream"})
                            continue
                        generator = RecordedGenerator(directory / "calls")
                        try:
                            if method == "rule":
                                pack = rule_pack(value)
                            elif method == "independent":
                                pack = independent_pack(value, generator)
                            elif method == "joint":
                                pack = joint_pack(value, generator)
                            else:
                                pack = fullchain.step(step, generator, directory)
                            write_new(directory / "pack.json", pack)
                            outcome: dict[str, Any] = {
                                "status": "completed",
                                "pack_sha256": digest(pack),
                                "calls": generator.calls,
                            }
                        except Exception as exc:
                            outcome = {
                                "status": "generation_failed",
                                "calls": generator.calls,
                                "error_type": type(exc).__name__,
                            }
                            if method == "fullchain":
                                blocked = True
                        write_new(directory / "outcome.json", outcome)
                finally:
                    if fullchain is not None:
                        fullchain.close()
    write_new(output / "completed.json", {"completed_at": now(), "units": len(planned)})


def configured_database() -> str | None:
    return os.getenv("EVAL_DATABASE_URL")
