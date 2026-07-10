import json
from typing import Any

from monobase.llm import LLMClientFactory, LLMConfig, ModelType
from monobase.llm.exceptions import ConfigurationError, LLMError

from app.core.config import settings


class LLMJsonGenerationError(RuntimeError):
    """Raised when the LLM call fails or does not return valid JSON."""


def should_use_real_llm() -> bool:
    return settings.llm_configured


def generate_json(system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.llm_configured:
        raise ConfigurationError(
            "LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL must be configured to call the LLM API."
        )

    config = LLMConfig(
        base_url=settings.llm_base_url or "",
        api_key=settings.llm_api_key or "",
        model=settings.llm_model or "",
        model_type=ModelType.TEXT,
        timeout=settings.llm_timeout,
        thinking=settings.llm_thinking,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
        },
    ]

    try:
        with LLMClientFactory.create(config) as client:
            raw = client.invoke(messages=messages, stream=False, validate_output=False)
    except LLMError as exc:
        raise LLMJsonGenerationError(f"LLM API call failed: {exc}") from exc

    return _parse_json_object(str(raw))


def _parse_json_object(raw: str) -> dict[str, Any]:
    content = raw.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3:
            content = "\n".join(lines[1:-1]).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMJsonGenerationError("LLM output does not contain a JSON object.")
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMJsonGenerationError("LLM output is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise LLMJsonGenerationError("LLM output JSON must be an object.")
    return parsed
