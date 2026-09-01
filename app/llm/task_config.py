from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import settings
from app.llm.client import (
    DEFAULT_TEMPERATURE,
    LLMConfigurationError,
    OpenAICompatibleLLMClient,
)
from app.prompts.template_registry import PROMPT_TEMPLATE_CONTRACTS

logger = logging.getLogger(__name__)


class LLMTaskConfig(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    model: str | None = None
    timeout: float | None = None
    stream_read_timeout: float | None = None
    use_response_format: bool | None = None
    structured_max_retries: int | None = Field(default=None, ge=0)
    temperature: float | None = None
    extra_params: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("provider", "base_url", "api_key", "api_key_env", "model", mode="before")
    @classmethod
    def _blank_string_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def merged_with(self, fallback: LLMTaskConfig) -> LLMTaskConfig:
        values: dict[str, Any] = {}
        for field_name in type(self).model_fields:
            own_value = getattr(self, field_name)
            fallback_value = getattr(fallback, field_name)
            values[field_name] = own_value if own_value is not None else fallback_value
        return LLMTaskConfig(**values)

    @property
    def resolved_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            env_value = os.getenv(self.api_key_env)
            if env_value and env_value.strip():
                return env_value.strip()
        return None

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.resolved_api_key and self.model)


class LLMTaskConfigMapping(BaseModel):
    defaults: LLMTaskConfig = Field(default_factory=LLMTaskConfig)
    tasks: dict[str, LLMTaskConfig] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("tasks")
    @classmethod
    def _validate_task_keys(cls, value: dict[str, LLMTaskConfig]) -> dict[str, LLMTaskConfig]:
        known_keys = known_llm_task_keys()
        unknown = sorted(set(value) - known_keys)
        if unknown:
            raise ValueError(f"Unknown LLM task key(s): {', '.join(unknown)}")
        return value


def known_llm_task_keys() -> set[str]:
    return {contract.name for contract in PROMPT_TEMPLATE_CONTRACTS}


def get_llm_task_config(task_key: str, overrides: dict[str, Any] | None = None) -> LLMTaskConfig:
    if task_key not in known_llm_task_keys():
        raise LLMConfigurationError(f"Unknown LLM task key: {task_key}.")
    mapping = load_llm_task_config_mapping()
    env_defaults = _settings_default_config()
    configured_defaults = mapping.defaults.merged_with(env_defaults)
    task_config = mapping.tasks.get(task_key, LLMTaskConfig()).merged_with(configured_defaults)
    if overrides:
        task_config = LLMTaskConfig(**overrides).merged_with(task_config)
    return task_config


def create_llm_client(
    task_key: str,
    overrides: dict[str, Any] | None = None,
) -> OpenAICompatibleLLMClient:
    config = get_llm_task_config(task_key, overrides=overrides)
    missing = []
    if not config.resolved_api_key:
        missing.append("LLM_API_KEY")
    if not config.base_url:
        missing.append("LLM_BASE_URL")
    if not config.model:
        missing.append("LLM_MODEL")
    if missing:
        raise LLMConfigurationError(
            f"Missing LLM configuration for task {task_key}: {', '.join(missing)}."
        )
    return OpenAICompatibleLLMClient(
        provider=config.provider,
        base_url=config.base_url,
        api_key=config.resolved_api_key,
        model=config.model,
        timeout=config.timeout,
        stream_read_timeout=config.stream_read_timeout,
        use_response_format=config.use_response_format,
        temperature=config.temperature,
        task_key=task_key,
    )


def is_llm_task_configured(task_key: str) -> bool:
    return get_llm_task_config(task_key).configured


@lru_cache
def load_llm_task_config_mapping() -> LLMTaskConfigMapping:
    path = _mapping_path()
    if path is None:
        return LLMTaskConfigMapping()
    if not path.exists():
        logger.info("llm.task_config.missing path=%s using_env_defaults=true", path)
        return LLMTaskConfigMapping()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LLMConfigurationError(f"LLM task config mapping is not valid JSON: {path}.") from exc
    if not isinstance(payload, dict):
        raise LLMConfigurationError("LLM task config mapping root must be a JSON object.")
    try:
        return LLMTaskConfigMapping.model_validate(payload)
    except ValidationError as exc:
        raise LLMConfigurationError(f"LLM task config mapping is invalid: {path}.") from exc


def clear_llm_task_config_cache() -> None:
    load_llm_task_config_mapping.cache_clear()


def _mapping_path() -> Path | None:
    raw_path = settings.llm_task_config_path
    if raw_path is None or not raw_path.strip():
        return None
    path = Path(raw_path.strip()).expanduser()
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _settings_default_config() -> LLMTaskConfig:
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


__all__ = [
    "LLMTaskConfig",
    "LLMTaskConfigMapping",
    "clear_llm_task_config_cache",
    "create_llm_client",
    "get_llm_task_config",
    "is_llm_task_configured",
    "known_llm_task_keys",
    "load_llm_task_config_mapping",
]
