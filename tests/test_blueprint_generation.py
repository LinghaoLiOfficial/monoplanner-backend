from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement


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
    assert blueprint["content"]["api_needs"][0]["resource"] == "projects"

    list_response = client.get(f"/api/v1/projects/{project['id']}/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/blueprints/{blueprint['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == blueprint["id"]


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
