from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.api_contract import ApiContractDraft
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun


def _create_project_with_blueprint(client: TestClient) -> dict:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Structured Drafts", "description": "demo"},
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "做一个可以把业务需求转成结构化上下文包的工具"},
    )
    blueprint_response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    assert blueprint_response.status_code == 201
    return project


def test_generate_list_and_read_api_contract(client: TestClient) -> None:
    project = _create_project_with_blueprint(client)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")

    assert response.status_code == 201
    draft = response.json()
    assert draft["project_id"] == project["id"]
    assert draft["version"] == 1
    assert draft["base_path"] == "/api/v1"
    assert draft["content"]["resources"][0]["name"] == "projects"
    assert draft["content"]["resources"][0]["endpoints"][0]["method"] == "POST"

    list_response = client.get(f"/api/v1/projects/{project['id']}/api-contracts")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/api-contracts/{draft['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == draft["id"]


def test_generate_list_and_read_db_model(client: TestClient) -> None:
    project = _create_project_with_blueprint(client)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/db-model")

    assert response.status_code == 201
    draft = response.json()
    assert draft["project_id"] == project["id"]
    assert draft["version"] == 1
    assert draft["content"]["database"]["engine"] == "PostgreSQL"
    assert draft["content"]["entities"][0]["name"] == "Project"

    list_response = client.get(f"/api/v1/projects/{project['id']}/db-models")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/db-models/{draft['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == draft["id"]


def test_generate_context_packs_filter_and_export(client: TestClient) -> None:
    project = _create_project_with_blueprint(client)
    client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")
    client.post(f"/api/v1/projects/{project['id']}/generate/db-model")

    response = client.post(f"/api/v1/projects/{project['id']}/generate/context-packs")

    assert response.status_code == 201
    packs = response.json()
    roles = {pack["role"] for pack in packs}
    assert roles == {"frontend_engineer", "backend_engineer"}
    assert "API Contract Subset" in next(
        pack["prompt_text"] for pack in packs if pack["role"] == "frontend_engineer"
    )

    list_response = client.get(f"/api/v1/projects/{project['id']}/context-packs")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2

    filtered_response = client.get(
        f"/api/v1/projects/{project['id']}/context-packs?role=frontend_engineer"
    )
    assert filtered_response.status_code == 200
    assert len(filtered_response.json()) == 1
    assert filtered_response.json()[0]["role"] == "frontend_engineer"

    pack_id = filtered_response.json()[0]["id"]
    detail_response = client.get(f"/api/v1/context-packs/{pack_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == pack_id

    export_response = client.post(f"/api/v1/context-packs/{pack_id}/export")
    assert export_response.status_code == 200
    export = export_response.json()
    assert export["filename"] == "frontend_engineer_context_pack.md"
    assert export["content_type"] == "text/markdown"
    assert "# Frontend Engineer Context Pack" in export["content"]


def test_context_packs_can_generate_with_missing_drafts(client: TestClient) -> None:
    project = _create_project_with_blueprint(client)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/context-packs")

    assert response.status_code == 201
    backend_pack = next(pack for pack in response.json() if pack["role"] == "backend_engineer")
    assert "DbModelDraft has not been generated yet" in backend_pack["prompt_text"]


def test_consistency_check_warning_then_passed(client: TestClient) -> None:
    project = _create_project_with_blueprint(client)

    warning_response = client.get(f"/api/v1/projects/{project['id']}/consistency-check")
    assert warning_response.status_code == 200
    assert warning_response.json()["status"] == "warning"

    client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")
    client.post(f"/api/v1/projects/{project['id']}/generate/db-model")
    client.post(f"/api/v1/projects/{project['id']}/generate/context-packs")

    passed_response = client.get(f"/api/v1/projects/{project['id']}/consistency-check")
    assert passed_response.status_code == 200
    assert passed_response.json()["status"] == "passed"


def test_structured_drafts_require_blueprint_and_record_failed_run(
    client: TestClient, db_session
) -> None:
    project = client.post("/api/v1/projects", json={"name": "No Blueprint"}).json()

    response = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")

    assert response.status_code == 400
    failed_run = db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_api_contract")
    )
    assert failed_run is not None
    assert failed_run.status == "failed"


def test_delete_project_cascades_structured_drafts(client: TestClient, db_session) -> None:
    project = _create_project_with_blueprint(client)
    client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")
    client.post(f"/api/v1/projects/{project['id']}/generate/db-model")
    client.post(f"/api/v1/projects/{project['id']}/generate/context-packs")

    delete_response = client.delete(f"/api/v1/projects/{project['id']}")

    assert delete_response.status_code == 204
    assert db_session.scalars(select(ApiContractDraft)).all() == []
    assert db_session.scalars(select(DbModelDraft)).all() == []
    assert db_session.scalars(select(ContextPack)).all() == []
