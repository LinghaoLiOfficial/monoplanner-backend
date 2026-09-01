import json

import pytest

from app.core.config import settings
from app.llm.client import LLMConfigurationError
from app.llm.task_config import (
    clear_llm_task_config_cache,
    create_llm_client,
    get_llm_task_config,
    load_llm_task_config_mapping,
)


@pytest.fixture(autouse=True)
def clear_task_config_cache():
    clear_llm_task_config_cache()
    yield
    clear_llm_task_config_cache()


def _write_mapping(tmp_path, payload: dict) -> str:
    path = tmp_path / "llm-task-mapping.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_task_config_overrides_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        settings,
        "llm_task_config_path",
        _write_mapping(
            tmp_path,
            {
                "defaults": {
                    "base_url": "https://default.test/v1",
                    "api_key": "default-key",
                    "model": "default-model",
                    "timeout": 60,
                },
                "tasks": {
                    "ui_design": {
                        "model": "ui-model",
                        "stream_read_timeout": 600,
                    }
                },
            },
        ),
    )

    config = get_llm_task_config("ui_design")

    assert config.base_url == "https://default.test/v1"
    assert config.resolved_api_key == "default-key"
    assert config.model == "ui-model"
    assert config.timeout == 60
    assert config.stream_read_timeout == 600


def test_task_config_falls_back_to_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_task_config_path", None)

    config = get_llm_task_config("blueprint_generator")

    assert config.provider == "openai_compatible"
    assert config.timeout is not None
    assert config.stream_read_timeout is not None


def test_api_key_env_is_resolved_and_task_api_key_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TASK_LLM_KEY", "env-key")
    monkeypatch.setattr(
        settings,
        "llm_task_config_path",
        _write_mapping(
            tmp_path,
            {
                "defaults": {
                    "base_url": "https://default.test/v1",
                    "api_key_env": "TASK_LLM_KEY",
                    "model": "default-model",
                },
                "tasks": {
                    "prompt_pack": {
                        "api_key": "task-key",
                    }
                },
            },
        ),
    )

    defaulted = get_llm_task_config("ui_design")
    overridden = get_llm_task_config("prompt_pack")

    assert defaulted.resolved_api_key == "env-key"
    assert overridden.resolved_api_key == "task-key"


def test_unknown_task_key_in_mapping_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        settings,
        "llm_task_config_path",
        _write_mapping(
            tmp_path,
            {
                "defaults": {},
                "tasks": {"missing_task": {"model": "bad"}},
            },
        ),
    )

    with pytest.raises(LLMConfigurationError):
        load_llm_task_config_mapping()


def test_unknown_task_key_lookup_raises() -> None:
    with pytest.raises(LLMConfigurationError):
        get_llm_task_config("missing_task")


def test_invalid_field_type_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        settings,
        "llm_task_config_path",
        _write_mapping(
            tmp_path,
            {
                "defaults": {"timeout": "not-a-number"},
                "tasks": {},
            },
        ),
    )

    with pytest.raises(LLMConfigurationError):
        load_llm_task_config_mapping()


def test_create_llm_client_uses_task_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        settings,
        "llm_task_config_path",
        _write_mapping(
            tmp_path,
            {
                "defaults": {
                    "base_url": "https://default.test/v1",
                    "api_key": "default-key",
                    "model": "default-model",
                    "timeout": 60,
                    "stream_read_timeout": 300,
                },
                "tasks": {
                    "ui_design": {
                        "base_url": "https://ui.test/v1",
                        "model": "ui-model",
                        "timeout": 30,
                        "temperature": 0.4,
                    }
                },
            },
        ),
    )

    client = create_llm_client("ui_design")

    assert client.metadata.task_key == "ui_design"
    assert client.metadata.base_url == "https://ui.test/v1"
    assert client.metadata.model == "ui-model"
    assert client.metadata.timeout == 30
    assert client.metadata.stream_read_timeout == 300
    assert client.metadata.temperature == 0.4
    assert client.metadata.has_api_key is True


def test_create_llm_client_requires_final_connection_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        settings,
        "llm_task_config_path",
        _write_mapping(
            tmp_path,
            {
                "defaults": {"model": "model-only"},
                "tasks": {},
            },
        ),
    )

    with pytest.raises(LLMConfigurationError):
        create_llm_client("blueprint_generator")
