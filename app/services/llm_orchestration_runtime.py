from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.llm.client import LLMResponseFormatError, OpenAICompatibleLLMClient
from app.llm.json_client import parse_json_object
from app.llm.structured_client import generate_structured_json
from app.services.llm_generation_runtime import (
    LLMPartialStreamError,
    collect_llm_stream_text,
)

JSON_OBJECT_RESPONSE_FORMAT = {"response_format": {"type": "json_object"}}


def generate_orchestration_json(
    system_prompt: str,
    user_payload: dict[str, Any] | str,
    *,
    response_model: type[BaseModel],
    llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
) -> dict[str, Any]:
    if llm_client_factory is None:
        return generate_structured_json(
            system_prompt,
            user_payload,
            response_model=response_model,
        )
    try:
        raw = collect_llm_stream_text(
            system_prompt,
            user_payload,
            llm_client_factory=llm_client_factory or OpenAICompatibleLLMClient,
            extra_params=JSON_OBJECT_RESPONSE_FORMAT,
        )
    except LLMPartialStreamError as exc:
        try:
            parsed = parse_json_object(exc.partial_text)
        except LLMResponseFormatError as parse_exc:
            raise exc from parse_exc
        return response_model.model_validate(parsed).model_dump(mode="json")
    parsed = parse_json_object(raw)
    return response_model.model_validate(parsed).model_dump(mode="json")
