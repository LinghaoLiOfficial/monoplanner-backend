import json
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.llm.client import (
    LLMConfigurationError,
    LLMRequestError,
    extract_chat_completion_stream_delta,
)
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun
from app.schemas.business_requirement_story import GenerateBusinessRequirementStoriesRequest
from app.services.streaming_generation_service import StreamingGenerationService
from tests.llm_stream_helpers import patch_llm_stream
from tests.test_blueprint_generation import _mock_blueprint_content
from tests.test_business_requirement_stories import VALID_LLM_OUTPUT_DICT
from tests.test_structured_drafts import _mock_api_contract_content, _mock_db_model_content


def _events(response) -> list[dict]:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["connection"] == "keep-alive"
    assert response.headers["x-accel-buffering"] == "no"
    events = []
    for block in response.text.strip().split("\n\n"):
        assert block.startswith("data: ")
        events.append(json.loads(block.removeprefix("data: ")))
    return events


def _stream_json(payload: dict):
    raw = json.dumps(payload, ensure_ascii=False)
    midpoint = max(1, len(raw) // 2)
    yield raw[:midpoint]
    yield raw[midpoint:]


def _get_blueprint_run(db_session):
    return db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_blueprint")
    )


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


def _create_project_with_blueprint(client: TestClient, monkeypatch) -> dict:
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = _create_project_with_requirement(client)
    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    assert response.status_code == 201
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


def test_stream_blueprint_saves_resource_and_records_run(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(_mock_blueprint_content()),
    )

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint/stream")

    events = _events(response)
    assert [event["type"] for event in events] == ["start", "saved", "done"]
    assert events[0]["module"] == "blueprint"
    assert events[-2]["resource"]["project_id"] == project["id"]
    assert events[-2]["resource"]["version"] == 1
    run = _get_blueprint_run(db_session)
    assert run is not None
    assert run.status == "completed"


def test_regular_blueprint_endpoint_uses_internal_stream_and_returns_json(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    raw = json.dumps(_mock_blueprint_content(), ensure_ascii=False)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: iter([f"```json\n{raw}\n```"]),
    )

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 201
    assert not response.headers["content-type"].startswith("text/event-stream")
    assert response.json()["project_id"] == project["id"]
    run = _get_blueprint_run(db_session)
    assert run is not None
    assert run.status == "completed"
    assert run.output_snapshot["raw_text_length"] > len(raw)
    assert run.output_snapshot["resource_id"] == response.json()["id"]
    assert run.output_snapshot["counts"]["pages"] == 1


def test_stream_business_stories_saves_items(client: TestClient, db_session, monkeypatch) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(VALID_LLM_OUTPUT_DICT),
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories/stream",
        json={},
    )

    events = _events(response)
    assert [event["type"] for event in events] == ["start", "saved", "done"]
    assert events[-2]["type"] == "saved"
    assert events[0]["progress"] == 0
    assert {event["progress"] for event in events} == {0, 100}
    assert events[-2]["progress"] == 100
    assert events[-1]["progress"] == 100
    assert events[-1]["message"] == "业务需求故事已更新。"
    assert len(events[-2]["resource"]["items"]) == 2
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "completed"
    assert str(run.requirement_id) == project["requirement_id"]
    assert run.progress == 100
    stories = db_session.scalars(select(BusinessRequirementStory)).all()
    assert len(stories) == 2
    assert {str(story.requirement_id) for story in stories} == {project["requirement_id"]}
    assert {str(story.project_id) for story in stories} == {project["id"]}


def test_regular_business_stories_endpoint_records_completed_snapshot(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(VALID_LLM_OUTPUT_DICT),
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 201
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


def test_stream_api_contract_and_db_model_save_resources(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_blueprint(client, monkeypatch)

    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(_mock_api_contract_content()),
    )
    api_response = client.post(
        f"/api/v1/projects/{project['id']}/generate/api-contract/stream"
    )
    api_events = _events(api_response)
    assert api_events[-2]["resource"]["base_path"] == "/api/v1"

    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(_mock_db_model_content()),
    )
    db_response = client.post(f"/api/v1/projects/{project['id']}/generate/db-model/stream")
    db_events = _events(db_response)
    assert db_events[-2]["resource"]["content"]["database"]["engine"] == "PostgreSQL"

    run_types = {
        run.run_type: run.status
        for run in db_session.scalars(select(GenerationRun)).all()
    }
    assert run_types["generate_api_contract"] == "completed"
    assert run_types["generate_db_model"] == "completed"


def test_stream_returns_error_event_and_records_failed_run(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)

    def fail_stream(*_args, **_kwargs):
        raise LLMConfigurationError("missing config")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_stream)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint/stream")

    events = _events(response)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "llm_not_configured"
    assert events[-1]["status"] == 503
    run = _get_blueprint_run(db_session)
    assert run is not None
    assert run.status == "failed"
    assert run.output_snapshot["failure_stage"] == "llm_request"


def test_stream_maps_request_failure_to_error_event(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)

    def fail_stream(*_args, **_kwargs):
        raise LLMRequestError("upstream failed")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_stream)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint/stream")

    events = _events(response)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "llm_request_failed"
    assert events[-1]["status"] == 502
    run = _get_blueprint_run(db_session)
    assert run is not None
    assert run.status == "failed"
    assert run.output_snapshot["failure_stage"] == "llm_request"
    assert run.error_message == "upstream failed"


def test_stream_maps_invalid_json_to_error_event(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: iter(["not json"]),
    )

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint/stream")

    events = _events(response)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "llm_output_format_invalid"
    assert events[-1]["status"] == 502
    run = _get_blueprint_run(db_session)
    assert run is not None
    assert run.status == "failed"
    assert run.output_snapshot["failure_stage"] == "parse"
    assert run.output_snapshot["raw_text_length"] == len("not json")


def test_stream_business_stories_fails_when_no_valid_story(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json({"stories": []}),
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories/stream",
        json={"requirement_id": project["requirement_id"]},
    )

    events = _events(response)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "llm_output_format_invalid"
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"
    assert run.message == "业务需求故事更新失败"
    assert run.error_message == "未生成有效业务需求故事。"
    assert db_session.scalars(select(BusinessRequirementStory)).all() == []


def test_stream_business_stories_records_failed_run_when_save_fails(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(VALID_LLM_OUTPUT_DICT),
    )

    def fail_add(instance):
        if isinstance(instance, BusinessRequirementStory):
            raise RuntimeError("database write failed")
        db_session.__class__.add(db_session, instance)

    monkeypatch.setattr(db_session, "add", fail_add)

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories/stream",
        json={"requirement_id": project["requirement_id"]},
    )

    events = _events(response)
    assert events[-1]["type"] == "error"
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"
    assert run.message == "业务需求故事更新失败"
    assert run.error_message == "database write failed"
    assert run.progress < 100


def test_stream_compat_does_not_emit_delta_events(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: _stream_json(VALID_LLM_OUTPUT_DICT),
    )
    service = StreamingGenerationService(db_session)
    spec = service.build_business_stories_spec(
        project_id=UUID(project["id"]),
        payload=GenerateBusinessRequirementStoriesRequest(
            requirement_id=UUID(project["requirement_id"])
        ),
    )
    stream = service.stream(spec)

    start_event = json.loads(next(stream).removeprefix("data: "))
    saved_event = json.loads(next(stream).removeprefix("data: "))
    done_event = json.loads(next(stream).removeprefix("data: "))

    assert start_event["type"] == "start"
    assert saved_event["type"] == "saved"
    assert done_event["type"] == "done"
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "completed"
    assert run.progress == 100
