from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement


def test_generate_blueprint_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/generate/blueprint"
    )

    assert response.status_code == 404


def test_generate_blueprint_requires_requirement(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "No Req"}).json()

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 400


def test_generate_and_read_blueprint(client: TestClient) -> None:
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
    assert blueprint["title"] == "项目蓝图草案"
    assert blueprint["content"]["project"]["name"] == "Blueprint Project"
    assert "Next.js" in blueprint["content"]["tech_stack"]["frontend"]
    assert "FastAPI" in blueprint["content"]["tech_stack"]["backend"]
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

    def fail_generation(*_args, **_kwargs) -> dict[str, object]:
        raise AttributeError("'Project' object has no attribute 'frontend_stack'")

    monkeypatch.setattr(
        "app.services.generation_service.build_mock_blueprint_content",
        fail_generation,
    )

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 500
    assert response.json()["detail"] == "生成蓝图草案失败，请检查项目数据或稍后重试。"
    run = db_session.scalar(select(GenerationRun).where(GenerationRun.status == "failed"))
    assert run is not None
    assert "frontend_stack" in (run.error_message or "")


def test_delete_project_cascades_related_records(client: TestClient, db_session) -> None:
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
