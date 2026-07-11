import json
from collections.abc import Iterator
from typing import Any


def stream_json_payload(payload: dict[str, Any]) -> Iterator[str]:
    raw = json.dumps(payload, ensure_ascii=False)
    midpoint = max(1, len(raw) // 2)
    yield raw[:midpoint]
    yield raw[midpoint:]


def patch_llm_stream(monkeypatch, payload: dict[str, Any]) -> None:
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: stream_json_payload(payload),
    )


def patch_llm_stream_sequence(monkeypatch, *payloads: dict[str, Any]) -> None:
    remaining = list(payloads)

    def stream(*_args, **_kwargs):
        if not remaining:
            raise AssertionError("No mocked LLM stream payload remaining.")
        return stream_json_payload(remaining.pop(0))

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", stream)
