from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.llm.client import (
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMRequestError,
    LLMResponseFormatError,
    OpenAICompatibleLLMClient,
)

logger = logging.getLogger(__name__)


class LLMJsonGenerationError(LLMResponseFormatError):
    """Raised when the LLM returns content that cannot be parsed as a JSON object."""


def should_use_real_llm() -> bool:
    return settings.llm_configured


def generate_json(
    system_prompt: str,
    user_payload: dict[str, Any] | str,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client = OpenAICompatibleLLMClient()
    raw = client.invoke(system_prompt, user_payload, extra_params=extra_params)
    return parse_json_object(raw)


def parse_json_object(raw: str) -> dict[str, Any]:
    content = clean_json_content(raw)
    if not content:
        raise LLMEmptyResponseError("LLM output content is empty.")

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        logger.warning(
            "llm.response.invalid reason=no_json_object content_excerpt=%s",
            _excerpt(content, 1000),
        )
        raise LLMJsonGenerationError("LLM output does not contain a JSON object.")

    candidate = content[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        logger.warning(
            "llm.response.invalid reason=invalid_json error=%s pos=%s content_excerpt=%s",
            exc.msg,
            exc.pos,
            _excerpt(candidate, 1000),
        )
        raise LLMJsonGenerationError(
            f"LLM output is not valid JSON: {exc.msg} at char {exc.pos}."
        ) from exc
    if not isinstance(parsed, dict):
        logger.warning("llm.response.invalid reason=json_not_object")
        raise LLMJsonGenerationError("LLM output JSON must be an object.")
    return parsed


def clean_json_content(raw: str) -> str:
    content = raw.strip()
    fenced_match = re.fullmatch(r"```(?:json|JSON)?\s*(.*?)\s*```", content, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()
    return content


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


__all__ = [
    "LLMConfigurationError",
    "LLMEmptyResponseError",
    "LLMJsonGenerationError",
    "LLMRequestError",
    "LLMResponseFormatError",
    "clean_json_content",
    "generate_json",
    "parse_json_object",
    "should_use_real_llm",
]
