"""Bounded, recorded model calls. No grading and no semantic repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from app.llm.client import build_chat_completions_url, extract_chat_completion_content
from app.llm.task_config import create_llm_client, get_llm_task_config
from evals.storage import digest, now, write_new

EXPECTED_MODEL = "openai/gpt-5-mini"


def public_config(task_key: str) -> dict[str, Any]:
    config = get_llm_task_config(task_key)
    return {
        "task_key": task_key,
        "model": config.model,
        "temperature": config.temperature,
        "structured_max_retries": config.structured_max_retries,
        "provider": config.provider,
        "endpoint_host": urlsplit(config.base_url or "").hostname,
        "timeout": config.timeout,
        "stream_read_timeout": config.stream_read_timeout,
        "use_response_format": config.use_response_format,
        "extra_params_sha256": digest(config.extra_params or {}),
    }


class RecordedGenerator:
    def __init__(self, directory: Path):
        self.directory = directory
        self.calls = 0

    def __call__(
        self,
        system: str,
        user: str | dict[str, Any],
        *,
        response_model: type[BaseModel],
        task_key: str,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = get_llm_task_config(task_key)
        if config.model != EXPECTED_MODEL:
            raise ValueError(f"{task_key}: expected {EXPECTED_MODEL}, got {config.model}")
        retries = config.structured_max_retries if config.structured_max_retries is not None else 2
        if retries > 2:
            raise ValueError("Evaluation allows at most two structured retries")
        client = create_llm_client(task_key)
        client._validate_configuration()
        extras = dict(config.extra_params or {})
        extras.update(extra_params or {})
        if set(extras) & {"model", "messages", "stream", "temperature"}:
            raise ValueError(
                "Extra parameters cannot override model, messages, stream or temperature"
            )
        body = client._build_request_body(system, user, extras)
        # The schema is appended for every arm; retries only request structural correction.
        body["messages"][0]["content"] += "\nReturn JSON matching this schema:\n" + json.dumps(
            response_model.model_json_schema(), ensure_ascii=False
        )

        def redact(value):
            if isinstance(value, str):
                return value.replace(client.api_key, "[REDACTED]")
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            return value

        for attempt in range(retries + 1):
            self.calls += 1
            prefix = self.directory / f"call-{self.calls:04d}"
            write_new(
                prefix.with_suffix(".request.json"),
                redact(
                    {
                        "created_at": now(),
                        "attempt": attempt + 1,
                        "config": public_config(task_key),
                        "body": body,
                        "body_sha256": digest(body),
                    }
                ),
            )
            try:
                response = httpx.post(
                    build_chat_completions_url(client.base_url),
                    headers={"Authorization": f"Bearer {client.api_key}"},
                    json=body,
                    timeout=httpx.Timeout(client.timeout, read=client.stream_read_timeout),
                )
            except httpx.HTTPError as exc:
                write_new(
                    prefix.with_suffix(".response.json"),
                    {
                        "created_at": now(),
                        "error_type": type(exc).__name__,
                        "usage": None,
                        "status": "transport_failed",
                    },
                )
                raise RuntimeError("Recorded model transport failed; see audit files") from None
            try:
                raw = response.json()
            except ValueError:
                raw = {"non_json_body": response.text}
            write_new(
                prefix.with_suffix(".response.json"),
                redact(
                    {
                        "created_at": now(),
                        "http_status": response.status_code,
                        "raw": raw,
                        "usage": raw.get("usage") if isinstance(raw, dict) else None,
                    }
                ),
            )
            if not response.is_success:
                raise RuntimeError(
                    f"Model returned HTTP {response.status_code}; no automatic retry"
                )
            try:
                parsed = response_model.model_validate_json(
                    extract_chat_completion_content(response)
                ).model_dump(mode="json")
            except ValueError as exc:
                write_new(
                    prefix.with_suffix(".validation.json"),
                    redact(
                        {
                            "status": "invalid_schema",
                            "error_type": type(exc).__name__,
                            "detail": str(exc),
                        }
                    ),
                )
                if attempt == retries:
                    raise ValueError("Structured output retries exhausted") from None
                body["messages"].append(
                    {
                        "role": "user",
                        "content": "Previous response did not match the schema. "
                        "Return one valid JSON object matching the supplied schema.",
                    }
                )
                continue
            write_new(prefix.with_suffix(".parsed.json"), redact(parsed))
            return parsed
        raise AssertionError("Unreachable")

    def client_factory(self, task_key: str):
        generator = self

        class RecordedClient:
            def stream(self, system, user, extra_params=None):
                from evals.fullchain import RESPONSE_MODELS

                yield json.dumps(
                    generator(
                        system,
                        user,
                        response_model=RESPONSE_MODELS[task_key],
                        task_key=task_key,
                        extra_params=extra_params,
                    ),
                    ensure_ascii=False,
                )

        return RecordedClient
