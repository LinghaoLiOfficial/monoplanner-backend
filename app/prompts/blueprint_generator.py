from __future__ import annotations

from typing import Any

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK, normalize_stack
from app.prompts.renderer import RenderedPrompt, render_prompt_template
from app.prompts.templates.blueprint_generator.output_schema import ProjectBlueprintOutput

TEMPLATE_NAME = "blueprint_generator"
SYSTEM_PROMPT = TEMPLATE_NAME


def build_blueprint_generation_payload(
    project: Any,
    requirement: Any,
    business_stories: list[dict[str, Any]],
) -> dict[str, Any]:
    frontend_stack = normalize_stack(
        getattr(project, "target_frontend_stack", None),
        DEFAULT_FRONTEND_STACK,
    )
    backend_stack = normalize_stack(
        getattr(project, "target_backend_stack", None),
        DEFAULT_BACKEND_STACK,
    )
    return {
        "project_name": project.name,
        "project_description": project.description or "",
        "target_frontend_stack": frontend_stack,
        "target_backend_stack": backend_stack,
        "latest_requirement": {
            "id": str(requirement.id),
            "raw_text": requirement.raw_text,
            "language": requirement.language,
            "source_type": requirement.source_type,
        },
        "business_stories": business_stories,
        "target_output_schema": ProjectBlueprintOutput.model_json_schema(),
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
