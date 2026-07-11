from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.llm.client import OpenAICompatibleLLMClient

logger = logging.getLogger(__name__)


def collect_llm_stream_text(
    system_prompt: str,
    user_payload: dict[str, Any],
    *,
    llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Collect a streaming chat completion into a single backend-only text blob."""
    client_factory = llm_client_factory or OpenAICompatibleLLMClient
    chunks: list[str] = []
    for delta in client_factory().stream(
        system_prompt,
        user_payload,
        extra_params=extra_params,
    ):
        chunks.append(delta)

    raw_text = "".join(chunks)
    logger.info(
        "llm_generation_runtime.collect.complete raw_text_length=%s raw_text_excerpt=%s",
        len(raw_text),
        _excerpt(raw_text, 200),
    )
    return raw_text


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
