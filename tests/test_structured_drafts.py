from fastapi.testclient import TestClient
from sqlalchemy import select

from app.llm.client import LLMConfigurationError, LLMResponseFormatError
from app.models.api_contract import ApiContractDraft
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from tests.llm_stream_helpers import patch_llm_stream, patch_llm_stream_sequence
from tests.queue_helpers import run_generation_job_in_new_session


def _mock_blueprint_content() -> dict:
    return {
        "project": {
            "name": "Structured Drafts",
            "one_liner": "结构化上下文包工具",
            "target_users": ["产品型开发者"],
            "business_goal": "生成结构化草案",
            "tech_stack": {"frontend": "Next.js", "backend": "FastAPI"},
        },
        "product_goals": [{"goal": "生成草案", "priority": "must_have"}],
        "user_roles": [
            {"name": "产品型开发者", "description": "审查草案", "permissions": ["review"]}
        ],
        "core_modules": [
            {"name": "项目", "description": "管理项目", "features": ["项目列表"]}
        ],
        "domain_entities": [
            {
                "name": "Project",
                "description": "项目",
                "fields": [
                    {"name": "id", "type": "uuid", "required": True, "description": "ID"},
                    {"name": "name", "type": "string", "required": True, "description": "名称"},
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
            {"resource": "projects", "operations": ["create", "read", "list"], "consumers": []}
        ],
        "business_requirement_stories": [],
        "non_functional_requirements": {},
        "assumptions": [],
        "open_questions": [],
    }


def _mock_api_contract_content() -> dict:
    return {
        "base_path": "/api/v1",
        "resources": [
            {
                "name": "projects",
                "description": "Manage projects",
                "endpoints": [
                    {
                        "method": "POST",
                        "path": "/projects",
                        "operation_id": "create_project",
                        "purpose": "Create project",
                        "request_body": "CreateProjectRequest",
                        "response_body": "ProjectResponse",
                        "auth_required": True,
                        "errors": ["400", "401", "409", "500"],
                    }
                ],
            }
        ],
        "schemas": [
            {
                "name": "CreateProjectRequest",
                "fields": [
                    {
                        "name": "name",
                        "type": "string",
                        "required": True,
                        "description": "Project name",
                    }
                ],
            }
        ],
        "error_model": {
            "name": "ApiError",
            "fields": [
                {"name": "code", "type": "string", "required": True},
                {"name": "message", "type": "string", "required": True},
            ],
        },
        "notes": ["Generated from blueprint"],
    }


def _mock_db_model_content() -> dict:
    return {
        "database": {
            "engine": "PostgreSQL",
            "orm": "SQLAlchemy 2.x",
            "migration_tool": "Alembic",
        },
        "entities": [
            {
                "name": "Project",
                "table_name": "projects",
                "description": "Project entity",
                "fields": [
                    {
                        "name": "name",
                        "type": "string",
                        "primary_key": False,
                        "nullable": False,
                        "description": "Project name",
                    }
                ],
                "relationships": [],
            }
        ],
        "relationships": [],
        "indexes": [{"table": "projects", "fields": ["name"], "reason": "Lookup by name"}],
        "migration_notes": ["Use UUID primary keys."],
    }


def _patch_structured_generators(monkeypatch) -> None:
    patch_llm_stream_sequence(
        monkeypatch,
        _mock_blueprint_content(),
        _mock_api_contract_content(),
        _mock_db_model_content(),
    )


def _create_project_with_blueprint(
    client: TestClient, monkeypatch, *, patch_blueprint: bool = True
) -> dict:
    if patch_blueprint:
        patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = client.post(
        "/api/v1/projects",
        json={"name": "Structured Drafts", "description": "demo"},
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "做一个可以把业务需求转成结构化上下文包的工具"},
    )
    blueprint_response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    assert blueprint_response.status_code == 202
    run_generation_job_in_new_session(blueprint_response.json()["id"])
    return project


def test_generate_list_and_read_api_contract(client: TestClient, monkeypatch) -> None:
    patch_llm_stream_sequence(monkeypatch, _mock_blueprint_content(), _mock_api_contract_content())
    project = _create_project_with_blueprint(client, monkeypatch, patch_blueprint=False)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    draft = client.get(f"/api/v1/projects/{project['id']}/api-contracts").json()[0]
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


def test_generate_list_and_read_db_model(client: TestClient, monkeypatch) -> None:
    patch_llm_stream_sequence(monkeypatch, _mock_blueprint_content(), _mock_db_model_content())
    project = _create_project_with_blueprint(client, monkeypatch, patch_blueprint=False)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/db-model")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    draft = client.get(f"/api/v1/projects/{project['id']}/db-models").json()[0]
    assert draft["project_id"] == project["id"]
    assert draft["version"] == 1
    assert draft["content"]["database"]["engine"] == "PostgreSQL"
    assert draft["content"]["entities"][0]["name"] == "Project"
    assert draft["content"]["entities"][0]["fields"][0]["name"] == "id"

    list_response = client.get(f"/api/v1/projects/{project['id']}/db-models")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/v1/db-models/{draft['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == draft["id"]


def test_generate_context_packs_filter_and_export(client: TestClient, monkeypatch) -> None:
    _patch_structured_generators(monkeypatch)
    project = _create_project_with_blueprint(client, monkeypatch, patch_blueprint=False)
    api_run = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract").json()
    run_generation_job_in_new_session(api_run["id"])
    db_run = client.post(f"/api/v1/projects/{project['id']}/generate/db-model").json()
    run_generation_job_in_new_session(db_run["id"])

    response = client.post(f"/api/v1/projects/{project['id']}/generate/context-packs")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    packs = client.get(f"/api/v1/projects/{project['id']}/context-packs").json()
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


def test_context_packs_can_generate_with_missing_drafts(client: TestClient, monkeypatch) -> None:
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = _create_project_with_blueprint(client, monkeypatch, patch_blueprint=False)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/context-packs")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    packs = client.get(f"/api/v1/projects/{project['id']}/context-packs").json()
    backend_pack = next(pack for pack in packs if pack["role"] == "backend_engineer")
    assert "DbModelDraft has not been generated yet" in backend_pack["prompt_text"]


def test_consistency_check_warning_then_passed(client: TestClient, monkeypatch) -> None:
    _patch_structured_generators(monkeypatch)
    project = _create_project_with_blueprint(client, monkeypatch, patch_blueprint=False)

    warning_response = client.get(f"/api/v1/projects/{project['id']}/consistency-check")
    assert warning_response.status_code == 200
    assert warning_response.json()["status"] == "warning"

    api_run = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract").json()
    run_generation_job_in_new_session(api_run["id"])
    db_run = client.post(f"/api/v1/projects/{project['id']}/generate/db-model").json()
    run_generation_job_in_new_session(db_run["id"])
    pack_run = client.post(f"/api/v1/projects/{project['id']}/generate/context-packs").json()
    run_generation_job_in_new_session(pack_run["id"])

    passed_response = client.get(f"/api/v1/projects/{project['id']}/consistency-check")
    assert passed_response.status_code == 200
    assert passed_response.json()["status"] == "passed"


def test_structured_drafts_require_blueprint_and_record_failed_run(
    client: TestClient, db_session
) -> None:
    project = client.post("/api/v1/projects", json={"name": "No Blueprint"}).json()

    response = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")

    assert response.status_code == 400
    assert db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_api_contract")
    ) is None


def test_api_contract_returns_503_and_records_failed_run(
    client: TestClient, db_session, monkeypatch
) -> None:
    project = _create_project_with_blueprint(client, monkeypatch)

    def fail_config(*_args, **_kwargs):
        raise LLMConfigurationError("missing config")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_config)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    run = db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_api_contract")
    )
    assert run is not None
    assert run.status == "failed"


def test_db_model_returns_502_and_records_failed_run(
    client: TestClient, db_session, monkeypatch
) -> None:
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    project = _create_project_with_blueprint(client, monkeypatch)

    def fail_format(*_args, **_kwargs):
        raise LLMResponseFormatError("bad json")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_format)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/db-model")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    run = db_session.scalar(
        select(GenerationRun).where(GenerationRun.run_type == "generate_db_model")
    )
    assert run is not None
    assert run.status == "failed"


def test_delete_project_cascades_structured_drafts(
    client: TestClient, db_session, monkeypatch
) -> None:
    _patch_structured_generators(monkeypatch)
    project = _create_project_with_blueprint(client, monkeypatch, patch_blueprint=False)
    api_run = client.post(f"/api/v1/projects/{project['id']}/generate/api-contract").json()
    run_generation_job_in_new_session(api_run["id"])
    db_run = client.post(f"/api/v1/projects/{project['id']}/generate/db-model").json()
    run_generation_job_in_new_session(db_run["id"])
    pack_run = client.post(f"/api/v1/projects/{project['id']}/generate/context-packs").json()
    run_generation_job_in_new_session(pack_run["id"])

    delete_response = client.delete(f"/api/v1/projects/{project['id']}")

    assert delete_response.status_code == 204
    assert db_session.scalars(select(ApiContractDraft)).all() == []
    assert db_session.scalars(select(DbModelDraft)).all() == []
    assert db_session.scalars(select(ContextPack)).all() == []
