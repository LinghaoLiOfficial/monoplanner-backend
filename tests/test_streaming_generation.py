import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select

from app.llm.client import (
    LLMRequestError,
    OpenAICompatibleLLMClient,
    extract_chat_completion_stream_delta,
)
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun
from app.services.llm_generation_runtime import LLMPartialStreamError
from app.services.llm_orchestration_runtime import generate_orchestration_json
from tests.llm_stream_helpers import patch_llm_stream
from tests.queue_helpers import run_generation_job_in_new_session
from tests.test_blueprint_generation import _mock_blueprint_content
from tests.test_business_requirement_stories import VALID_LLM_OUTPUT_DICT


class OkOutput(BaseModel):
    ok: bool


def _create_project_with_requirement(client: TestClient) -> dict:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Stream Project", "description": "demo"},
    ).json()
    requirement = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "做一个可以把业务需求转成结构化上下文包的工具"},
    ).json()
    project["requirement_id"] = requirement["id"]
    return project


def test_extract_chat_completion_stream_delta_parses_openai_chunks() -> None:
    line = 'data: {"choices":[{"delta":{"content":"hello"}}]}'

    assert extract_chat_completion_stream_delta(line) == "hello"
    assert extract_chat_completion_stream_delta("data: [DONE]") is None
    assert extract_chat_completion_stream_delta(": ping") is None
    assert extract_chat_completion_stream_delta('data: {"choices":[]}') is None
    assert extract_chat_completion_stream_delta('data: {"usage":{"total_tokens":10}}') is None
    assert extract_chat_completion_stream_delta(
        'data: {"choices":[{"message":{"content":"from message"}}]}'
    ) == "from message"
    assert extract_chat_completion_stream_delta(
        'data: {"choices":[{"text":"from text"}]}'
    ) == "from text"
    assert extract_chat_completion_stream_delta("data: {bad json") is None


def test_stream_uses_dedicated_read_timeout_for_long_running_chunks() -> None:
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="test-model",
        timeout=90,
        stream_read_timeout=300,
    )

    timeout = client._stream_timeout()

    assert timeout.connect == 90
    assert timeout.write == 90
    assert timeout.pool == 90
    assert timeout.read == 300
    assert client.metadata.stream_read_timeout == 300


def test_llm_client_builds_string_and_dict_user_messages() -> None:
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="test-model",
    )

    string_body = client._build_request_body("system", "===USER===\nhello", None)
    dict_body = client._build_request_body("system", {"hello": "world"}, None)

    assert string_body["messages"][1]["content"] == "===USER===\nhello"
    assert dict_body["messages"][1]["content"] == '{\n  "hello": "world"\n}'


def test_orchestration_json_salvages_complete_partial_stream(monkeypatch) -> None:
    def stream(_self, *_args, **_kwargs):
        yield '{"ok": true}'
        raise LLMRequestError("incomplete chunked read")

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", stream)

    assert generate_orchestration_json(
        "system",
        {"task": "demo"},
        response_model=OkOutput,
    ) == {"ok": True}


def test_orchestration_json_retries_incomplete_partial_stream(monkeypatch) -> None:
    def stream(_self, *_args, **_kwargs):
        yield '{"ok"'
        raise LLMRequestError("incomplete chunked read")

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", stream)

    with pytest.raises(LLMPartialStreamError):
        generate_orchestration_json("system", {"task": "demo"}, response_model=OkOutput)


def test_regular_blueprint_endpoint_enqueues_and_worker_saves_resource(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, _mock_blueprint_content())

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    run = run_generation_job_in_new_session(response.json()["id"])
    assert run.status == "completed"
    list_response = client.get(f"/api/v1/projects/{project['id']}/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    persisted = db_session.scalar(select(GenerationRun).where(GenerationRun.id == run.id))
    assert persisted.output_snapshot["resource_id"] == list_response.json()[0]["id"]


def test_regular_business_stories_endpoint_enqueues_and_status_maps_succeeded(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "completed"
    assert run.output_snapshot["raw_text_length"] > 0
    assert len(run.output_snapshot["resource_ids"]) == 2
    assert run.output_snapshot["counts"]["stories"] == 2
    status_response = client.get(
        f"/api/v1/requirements/{project['requirement_id']}/business-story-generation"
    )
    assert status_response.json()["status"] == "succeeded"
    assert len(db_session.scalars(select(BusinessRequirementStory)).all()) == 2


def test_stream_endpoints_are_gone(client: TestClient) -> None:
    project = _create_project_with_requirement(client)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint/stream")

    assert response.status_code == 410
    assert "已弃用" in response.json()["detail"]
