"""Prompt-pack generation from explicit snapshots, without persistence or cache lookup."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.prompts.orchestration import build_prompt_pack_prompt
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.services.orchestration_validators import validate_prompt_pack_payload

JsonGenerator = Callable[..., dict[str, Any]]


def generate_prompt_pack_content(
    *,
    project_config: dict[str, Any],
    selected_story: dict[str, Any] | None,
    change_sets: list[dict[str, Any]],
    old_versions: dict[str, Any],
    new_versions: dict[str, Any],
    generate_json: JsonGenerator,
    change_set: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = build_prompt_pack_prompt(
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set or (change_sets[0] if change_sets else {}),
        change_sets=change_sets,
        old_versions=old_versions,
        new_versions=new_versions,
        project_blueprint={},
    )
    parsed = generate_json(
        prompt.system, prompt.user, response_model=PromptPackOutput, task_key="prompt_pack"
    )
    return validate_prompt_pack_payload(parsed)


def schema_json(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()
