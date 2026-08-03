from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.llm.client import OpenAICompatibleLLMClient
from app.llm.json_client import parse_json_object
from app.services.llm_generation_runtime import collect_llm_stream_text

JSON_OBJECT_RESPONSE_FORMAT = {"response_format": {"type": "json_object"}}


def generate_orchestration_json(
    system_prompt: str,
    user_payload: dict[str, Any],
    *,
    llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
) -> dict[str, Any]:
    raw = collect_llm_stream_text(
        system_prompt,
        user_payload,
        llm_client_factory=llm_client_factory or OpenAICompatibleLLMClient,
        extra_params=JSON_OBJECT_RESPONSE_FORMAT,
    )
    return parse_json_object(raw)
