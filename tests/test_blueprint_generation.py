from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.llm.client import LLMConfigurationError, LLMResponseFormatError
from app.models.generation_run import GenerationRun
from app.models.project import Project
from app.models.requirement import Requirement
from app.prompts.blueprint_generator import build_blueprint_generation_payload
from tests.llm_stream_helpers import patch_llm_stream
from tests.queue_helpers import run_generation_job_in_new_session, run_next_generation_job


def _mock_blueprint_content() -> dict:
    return {
        "project": {
            "name": "Blueprint Project",
            "one_liner": "结构化上下文包工具",
            "target_users": ["产品型开发者"],
            "business_goal": "把业务需求转成可执行上下文",
            "tech_stack": {
                "frontend": [
                    {"name": "Next.js", "type": "framework"},
                    {"name": "React", "type": "ui_library"},
                    {"name": "TypeScript", "type": "language"},
                ],
                "backend": [
                    {"name": "FastAPI", "type": "framework"},
                    {"name": "SQLAlchemy", "type": "orm"},
                    {"name": "PostgreSQL", "type": "database"},
                ],
            },
        },
        "tech_stack": {
            "frontend": [
                {"name": "Next.js", "type": "framework"},
                {"name": "React", "type": "ui_library"},
                {"name": "TypeScript", "type": "language"},
            ],
            "backend": [
                {"name": "FastAPI", "type": "framework"},
                {"name": "SQLAlchemy", "type": "orm"},
                {"name": "PostgreSQL", "type": "database"},
            ],
        },
        "product_goals": [{"goal": "生成项目蓝图", "priority": "must_have"}],
        "user_roles": [
            {
                "name": "产品型开发者",
                "description": "审查生成结果",
                "permissions": ["review_blueprint"],
            }
        ],
        "core_modules": [
            {
                "name": "项目蓝图",
                "description": "整理结构化蓝图",
                "features": ["生成蓝图"],
            }
        ],
        "domain_entities": [
            {
                "name": "Project",
                "description": "用户创建的项目",
                "fields": [
                    {
                        "name": "id",
                        "type": "uuid",
                        "required": True,
                        "description": "Primary key",
                    }
                ],
                "relationships": [],
            }
        ],
        "pages": [
            {
                "path": "/projects",
                "name": "项目列表",
                "purpose": "查看项目",
                "components": ["ProjectList"],
                "data_dependencies": ["projects"],
            }
        ],
        "api_needs": [
            {
                "resource": "projects",
                "operations": ["create", "read", "list"],
                "consumers": ["项目列表"],
            }
        ],
        "business_requirement_stories": [],
        "non_functional_requirements": {
            "auth": "后续接入",
            "performance": "常规响应",
            "security": "保护用户数据",
            "observability": "记录生成日志",
        },
        "assumptions": [],
        "open_questions": [],
    }


def test_generate_blueprint_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/generate/blueprint"
    )

    assert response.status_code == 404


def test_generate_blueprint_requires_requirement(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "No Req"}).json()

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 400


def test_generate_and_read_blueprint(client: TestClient, monkeypatch) -> None:
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = client.post(
        "/api/v1/projects",
        json={"name": "Blueprint Project", "description": "demo"},
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "做一个可以把业务需求转成结构化上下文包的工具"},
    )

    generate_response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    assert generate_response.status_code == 202
    run_generation_job_in_new_session(generate_response.json()["id"])

    blueprint = client.get(f"/api/v1/projects/{project['id']}/blueprints").json()[0]
    assert blueprint["project_id"] == project["id"]
    assert blueprint["version"] == 1
    assert blueprint["title"] == "项目蓝图"
    assert blueprint["content"]["project"]["name"] == "Blueprint Project"
    assert blueprint["content"]["project"]["tech_stack"]["frontend"][0]["type"] == "framework"
    backend_stack = blueprint["content"]["project"]["tech_stack"]["backend"]
    assert backend_stack
    assert any(item["type"] == "framework" for item in backend_stack)
    assert blueprint["content"]["api_needs"][0]["resource"] == "projects"

    list_response = client.get(f"/api/v1/projects/{project['id']}/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/blueprints/{blueprint['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == blueprint["id"]


def test_generate_blueprint_uses_latest_project_target_stacks(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = client.post("/api/v1/projects", json={"name": "Latest Stacks"}).json()
    client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "target_frontend_stack": "Astro + React",
            "target_backend_stack": "FastAPI + SQLModel",
        },
    )
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "use the configured stacks"},
    )

    generate_response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    assert generate_response.status_code == 202
    run_generation_job_in_new_session(generate_response.json()["id"])

    run = db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_blueprint")
    )
    assert run is not None
    assert run.input_snapshot["target_frontend_stack"] == "Astro + React"
    assert run.input_snapshot["target_backend_stack"] == "FastAPI + SQLModel"
    assert run.input_snapshot["target_frontend_stack_items"][0]["type"] == "framework"
    blueprint = client.get(f"/api/v1/projects/{project['id']}/blueprints").json()[0]
    assert blueprint["content"]["project"]["tech_stack"]["frontend"][0]["name"] == "Astro"
    backend_stack = blueprint["content"]["project"]["tech_stack"]["backend"]
    assert any(item["name"] == "FastAPI" and item["type"] == "framework" for item in backend_stack)
    assert any(item["name"] == "SQLModel" and item["type"] == "orm" for item in backend_stack)


def test_blueprint_payload_defaults_blank_project_target_stacks(db_session, test_user) -> None:
    project = Project(
        owner_user_id=test_user.id,
        name="Blank Blueprint Stacks",
        target_frontend_stack="",
        target_backend_stack=" ",
    )
    requirement = Requirement(project=project, raw_text="blank stacks", language="zh-CN")
    db_session.add(project)
    db_session.add(requirement)
    db_session.commit()

    payload = build_blueprint_generation_payload(project, requirement, [])

    assert payload["target_frontend_stack"] == DEFAULT_FRONTEND_STACK
    assert payload["target_backend_stack"] == DEFAULT_BACKEND_STACK


def test_generate_blueprint_converts_generator_error_to_readable_500(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Generator Error"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "trigger error"},
    )

    def fail_generation(*_args, **_kwargs):
        raise AttributeError("'Project' object has no attribute 'frontend_stack'")

    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        fail_generation,
    )

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    run = db_session.scalar(select(GenerationRun).where(GenerationRun.status == "failed"))
    assert run is not None
    assert run.run_type == "generate_blueprint"
    assert "frontend_stack" in (run.error_message or "")


def test_generate_blueprint_returns_503_when_llm_unconfigured(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "No LLM"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "trigger config error"},
    )

    def fail_config(*_args, **_kwargs):
        raise LLMConfigurationError("missing config")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_config)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    run = db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_blueprint")
    )
    assert run is not None
    assert run.status == "failed"


def test_generate_blueprint_returns_502_when_llm_format_invalid(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Bad Blueprint"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "trigger format error"},
    )

    def fail_format(*_args, **_kwargs):
        raise LLMResponseFormatError("bad json")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_format)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    run = db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_blueprint")
    )
    assert run is not None
    assert run.status == "failed"


def test_delete_project_cascades_related_records(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = client.post("/api/v1/projects", json={"name": "Cascade"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "cascade requirement"},
    )
    client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    run_next_generation_job(db_session)

    delete_response = client.delete(f"/api/v1/projects/{project['id']}")

    assert delete_response.status_code == 204
    assert db_session.scalars(select(Requirement)).all() == []
    assert db_session.scalars(select(GenerationRun)).all() == []
