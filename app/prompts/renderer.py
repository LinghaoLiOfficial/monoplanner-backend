from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.prompts.template_registry import TEMPLATE_ROOT

SYSTEM_MARKER = "===SYSTEM==="
USER_MARKER = "===USER==="


class PromptTemplateRenderError(ValueError):
    """Raised when a prompt template cannot be rendered or split safely."""


@dataclass(frozen=True)
class RenderedPrompt:
    system: str
    user: str


def render_prompt_template(template_name: str, variables: dict[str, Any]) -> RenderedPrompt:
    template_path = f"{template_name}/prompt.j2"
    rendered = _environment().get_template(template_path).render(**variables).strip()
    return split_rendered_prompt(rendered, template_name=template_name)


def split_rendered_prompt(rendered: str, *, template_name: str = "<inline>") -> RenderedPrompt:
    system_count = rendered.count(SYSTEM_MARKER)
    user_count = rendered.count(USER_MARKER)
    if system_count != 1 or user_count != 1:
        raise PromptTemplateRenderError(
            f"Prompt template {template_name} must contain exactly one {SYSTEM_MARKER} "
            f"and exactly one {USER_MARKER}."
        )
    system_index = rendered.find(SYSTEM_MARKER)
    user_index = rendered.find(USER_MARKER)
    if system_index > user_index:
        raise PromptTemplateRenderError(
            f"Prompt template {template_name} must place {SYSTEM_MARKER} before {USER_MARKER}."
        )
    system = rendered[system_index + len(SYSTEM_MARKER) : user_index].strip()
    user = rendered[user_index + len(USER_MARKER) :].strip()
    if not system or not user:
        raise PromptTemplateRenderError(
            f"Prompt template {template_name} rendered empty system or user content."
        )
    return RenderedPrompt(system=system, user=user)


def tojson_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(Path(TEMPLATE_ROOT)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson_pretty"] = tojson_pretty
    return env


__all__ = [
    "PromptTemplateRenderError",
    "RenderedPrompt",
    "render_prompt_template",
    "split_rendered_prompt",
    "tojson_pretty",
]
