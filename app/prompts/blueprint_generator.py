from __future__ import annotations

from typing import Any

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.core.tech_stack import (
    normalize_tech_stack_items,
    tech_stack_items_to_payload,
    tech_stack_items_to_text,
)
from app.prompts.renderer import RenderedPrompt, render_prompt_template

TEMPLATE_NAME = "blueprint_generator"
SYSTEM_PROMPT = TEMPLATE_NAME


def build_blueprint_generation_payload(
    project: Any,
    requirement: Any,
    business_stories: list[dict[str, Any]],
) -> dict[str, Any]:
    frontend_items = normalize_tech_stack_items(
        getattr(project, "target_frontend_stack_items", None)
        or getattr(project, "target_frontend_stack", None)
        or DEFAULT_FRONTEND_STACK,
        infer_missing_type=True,
    )
    backend_items = normalize_tech_stack_items(
        getattr(project, "target_backend_stack_items", None)
        or getattr(project, "target_backend_stack", None)
        or DEFAULT_BACKEND_STACK,
        infer_missing_type=True,
    )
    return {
        "project_name": project.name,
        "target_frontend_stack": tech_stack_items_to_text(frontend_items) or DEFAULT_FRONTEND_STACK,
        "target_backend_stack": tech_stack_items_to_text(backend_items) or DEFAULT_BACKEND_STACK,
        "target_frontend_stack_items": tech_stack_items_to_payload(frontend_items),
        "target_backend_stack_items": tech_stack_items_to_payload(backend_items),
        "latest_requirement": {
            "id": str(requirement.id),
            "raw_text": requirement.raw_text,
            "language": requirement.language,
            "source_type": requirement.source_type,
        },
        "business_stories": business_stories,
    }


def build_blueprint_generation_prompt(
    project: Any,
    requirement: Any,
    business_stories: list[dict[str, Any]],
) -> RenderedPrompt:
    return render_prompt_template(
        TEMPLATE_NAME,
        build_blueprint_generation_payload(project, requirement, business_stories),
    )
