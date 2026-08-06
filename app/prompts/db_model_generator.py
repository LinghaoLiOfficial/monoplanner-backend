from __future__ import annotations

from typing import Any

from app.prompts.renderer import RenderedPrompt, render_prompt_template
from app.prompts.templates.db_model_generator.output_schema import DbModelOutput

TEMPLATE_NAME = "db_model_generator"
SYSTEM_PROMPT = TEMPLATE_NAME


def build_db_model_generation_payload(
    project: Any,
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "project_name": project.name,
        "blueprint_content": blueprint_content,
        "api_contract_content": api_contract_content,
        "target_backend_stack": project.target_backend_stack,
        "target_output_schema": DbModelOutput.model_json_schema(),
    }


def build_db_model_generation_prompt(
    project: Any,
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
) -> RenderedPrompt:
    return render_prompt_template(
        TEMPLATE_NAME,
        build_db_model_generation_payload(project, blueprint_content, api_contract_content),
    )
