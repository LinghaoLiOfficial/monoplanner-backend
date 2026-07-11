from fastapi.testclient import TestClient
from sqlalchemy import select

from app.llm.client import LLMConfigurationError, LLMResponseFormatError
from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement
from tests.llm_stream_helpers import patch_llm_stream


def _mock_blueprint_content() -> dict:
    return {
        "project": {
            "name": "Blueprint Project",
            "one_liner": "结构化上下文包工具",
            "target_users": ["产品型开发者"],
            "business_goal": "把业务需求转成可执行上下文",
            "tech_stack": {
                "frontend": "Next.js",
                "backend": "FastAPI",
            },
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

    assert generate_response.status_code == 201
    blueprint = generate_response.json()
    assert blueprint["project_id"] == project["id"]
    assert blueprint["version"] == 1
    assert blueprint["title"] == "项目蓝图"
    assert blueprint["content"]["project"]["name"] == "Blueprint Project"
    assert "Next.js" in blueprint["content"]["project"]["tech_stack"]["frontend"]
    assert "FastAPI" in blueprint["content"]["project"]["tech_stack"]["backend"]
    assert blueprint["content"]["api_needs"][0]["resource"] == "projects"

    list_response = client.get(f"/api/v1/projects/{project['id']}/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/blueprints/{blueprint['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == blueprint["id"]


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

    assert response.status_code == 500
    assert response.json()["detail"] == "生成失败，请检查项目数据或稍后重试。"
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

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "LLM 服务未配置，请检查 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL。"
    )
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

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM 返回的结构化结果格式不正确，请重试或调整模型配置。"
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

    delete_response = client.delete(f"/api/v1/projects/{project['id']}")

    assert delete_response.status_code == 204
    assert db_session.scalars(select(Requirement)).all() == []
    assert db_session.scalars(select(GenerationRun)).all() == []
