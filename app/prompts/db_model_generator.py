from __future__ import annotations

from typing import Any

from app.core.tech_stack import tech_stack_items_to_payload, tech_stack_items_to_text
from app.prompts.renderer import RenderedPrompt, render_prompt_template

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
        "target_backend_stack": tech_stack_items_to_text(
            getattr(project, "target_backend_stack_items", [])
        )
        or project.target_backend_stack,
        "target_backend_stack_items": tech_stack_items_to_payload(
            getattr(project, "target_backend_stack_items", [])
        ),
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
