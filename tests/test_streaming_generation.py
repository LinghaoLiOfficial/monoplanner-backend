from fastapi.testclient import TestClient
from sqlalchemy import select

from app.llm.client import extract_chat_completion_stream_delta
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun
from tests.llm_stream_helpers import patch_llm_stream
from tests.queue_helpers import run_generation_job_in_new_session
from tests.test_blueprint_generation import _mock_blueprint_content
from tests.test_business_requirement_stories import VALID_LLM_OUTPUT_DICT


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
