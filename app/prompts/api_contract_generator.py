from __future__ import annotations

from typing import Any

from app.core.llm_prompt_language import normalize_llm_prompt_language
from app.prompts.renderer import RenderedPrompt, render_prompt_template

TEMPLATE_NAME = "api_contract_generator"
SYSTEM_PROMPT = TEMPLATE_NAME


def build_api_contract_generation_payload(
    project: Any,
    blueprint_content: dict[str, Any],
) -> dict[str, Any]:
    return {
        "project_name": project.name,
        "blueprint_content": blueprint_content,
        "target_base_path": "/api/v1",
    }


def build_api_contract_generation_prompt(
    project: Any,
    blueprint_content: dict[str, Any],
) -> RenderedPrompt:
    return render_prompt_template(
        TEMPLATE_NAME,
        build_api_contract_generation_payload(project, blueprint_content),
        language=normalize_llm_prompt_language(getattr(project, "llm_prompt_language", None)),
    )
