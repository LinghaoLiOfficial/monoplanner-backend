from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import instructor
import openai
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.llm.client import (
    DEFAULT_TEMPERATURE,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMRequestError,
    LLMResponseFormatError,
    OpenAICompatibleLLMClient,
)
from app.llm.json_client import parse_json_object
from app.llm.task_config import (
    LLMTaskConfig,
    create_llm_client,
    get_llm_task_config,
    is_llm_task_configured,
)
from app.services.llm_generation_runtime import (
    LLMPartialStreamError,
    collect_llm_stream_text,
)

logger = logging.getLogger(__name__)

LLMClientFactory = Callable[[], OpenAICompatibleLLMClient]


def generate_structured_json(
    system_prompt: str,
    user_payload: dict[str, Any] | str,
    *,
    response_model: type[BaseModel],
    llm_client_factory: LLMClientFactory | None = None,
    max_retries: int | None = None,
    extra_params: dict[str, Any] | None = None,
    task_key: str | None = None,
) -> dict[str, Any]:
    configured = settings.llm_configured if task_key is None else is_llm_task_configured(task_key)
    if llm_client_factory is not None or not configured:
        return _generate_structured_json_from_stream(
            system_prompt,
            user_payload,
            response_model=response_model,
            llm_client_factory=llm_client_factory
            or _client_factory_for_task(task_key, configured=configured),
            extra_params=extra_params,
        )
    return _generate_structured_json_with_instructor(
        system_prompt,
        user_payload,
        response_model=response_model,
        max_retries=max_retries,
        task_key=task_key,
        extra_params=extra_params,
    )


def _generate_structured_json_with_instructor(
    system_prompt: str,
    user_payload: dict[str, Any] | str,
    *,
    response_model: type[BaseModel],
    max_retries: int | None,
    task_key: str | None,
    extra_params: dict[str, Any] | None,
) -> dict[str, Any]:
    config = _resolved_task_config(task_key)
    _validate_configuration(config, task_key=task_key)
    retries = (
        config.structured_max_retries
        if max_retries is None
        else max_retries
    )
    client = instructor.from_openai(
        openai.OpenAI(
            base_url=config.base_url,
            api_key=config.resolved_api_key,
            timeout=config.stream_read_timeout,
        ),
        mode=instructor.Mode.JSON,
    )
    request_kwargs: dict[str, Any] = dict(extra_params or {})
    request_kwargs.pop("response_format", None)
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _user_content(user_payload)},
            ],
            response_model=response_model,
            max_retries=retries,
            temperature=(
                config.temperature
                if config.temperature is not None
                else DEFAULT_TEMPERATURE
            ),
            **request_kwargs,
        )
    except ValidationError as exc:
        logger.warning(
            "llm.structured.validation_failed response_model=%s error=%s",
            response_model.__name__,
            _excerpt(str(exc), 500),
        )
        raise LLMResponseFormatError(
            f"LLM structured output failed schema validation: {response_model.__name__}."
        ) from exc
    except openai.APIError as exc:
        logger.warning(
            "llm.structured.request_failed response_model=%s error_type=%s message=%s",
            response_model.__name__,
            type(exc).__name__,
            _excerpt(str(exc), 500),
        )
        raise LLMRequestError("LLM API structured request failed.") from exc
    except Exception as exc:
        if _is_instructor_retry_error(exc):
            logger.warning(
                "llm.structured.retry_exhausted response_model=%s message=%s",
                response_model.__name__,
                _excerpt(str(exc), 500),
            )
            raise LLMResponseFormatError(
                f"LLM structured output failed schema validation: {response_model.__name__}."
            ) from exc
        raise
    if response is None:
        raise LLMEmptyResponseError("LLM structured response is empty.")
    return response.model_dump(mode="json")


def _generate_structured_json_from_stream(
    system_prompt: str,
    user_payload: dict[str, Any] | str,
    *,
    response_model: type[BaseModel],
    llm_client_factory: LLMClientFactory,
    extra_params: dict[str, Any] | None,
) -> dict[str, Any]:
    partial_error: LLMPartialStreamError | None = None
    try:
        raw = collect_llm_stream_text(
            system_prompt,
            user_payload,
            llm_client_factory=llm_client_factory,
            extra_params=extra_params,
        )
    except LLMPartialStreamError as exc:
        partial_error = exc
        raw = exc.partial_text
    try:
        parsed = parse_json_object(raw)
    except LLMResponseFormatError as exc:
        if partial_error is not None:
            raise partial_error from exc
        raise
    try:
        return response_model.model_validate(parsed).model_dump(mode="json")
    except ValidationError as exc:
        logger.warning(
            "llm.structured.stream_validation_failed response_model=%s error=%s",
            response_model.__name__,
            _excerpt(str(exc), 500),
        )
        raise LLMResponseFormatError(
            f"LLM structured output failed schema validation: {response_model.__name__}."
        ) from exc


def _resolved_task_config(task_key: str | None):
    if task_key is None:
        return LLMTaskConfig(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            stream_read_timeout=settings.llm_stream_read_timeout_seconds,
            use_response_format=settings.llm_use_response_format,
            structured_max_retries=settings.llm_structured_max_retries,
            temperature=DEFAULT_TEMPERATURE,
        )
    return get_llm_task_config(task_key)


def _client_factory_for_task(task_key: str | None, *, configured: bool) -> LLMClientFactory:
    if task_key is None or not configured:
        return OpenAICompatibleLLMClient
    return lambda: create_llm_client(task_key)


def _validate_configuration(config, *, task_key: str | None) -> None:
    missing = []
    if not config.resolved_api_key:
        missing.append("LLM_API_KEY")
    if not config.base_url:
        missing.append("LLM_BASE_URL")
    if not config.model:
        missing.append("LLM_MODEL")
    if missing:
        suffix = f" for task {task_key}" if task_key else ""
        raise LLMConfigurationError(
            f"Missing LLM configuration{suffix}: {', '.join(missing)}."
        )


def _user_content(user_payload: dict[str, Any] | str) -> str:
    if isinstance(user_payload, str):
        return user_payload
    import json

    return json.dumps(user_payload, ensure_ascii=False, indent=2)


def _is_instructor_retry_error(exc: Exception) -> bool:
    module = type(exc).__module__
    name = type(exc).__name__
    return module.startswith("instructor") or name in {"InstructorRetryException", "RetryError"}


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


__all__ = ["generate_structured_json"]
