from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.api_contract import ApiContractDraft
from app.models.blueprint import ProjectBlueprint
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.models.project import Project
from app.models.requirement import Requirement
from tests.llm_stream_helpers import patch_llm_stream_sequence


def _patch_generation_json(monkeypatch) -> None:
    patch_llm_stream_sequence(
        monkeypatch,
        {
            "project": {
                "name": "Cascade All",
                "one_liner": "Context workflow",
                "target_users": ["Builder"],
                "business_goal": "Generate context artifacts",
                "tech_stack": {"frontend": "Next.js", "backend": "FastAPI"},
            },
            "product_goals": [{"goal": "Generate artifacts", "priority": "must_have"}],
            "user_roles": [{"name": "Builder", "description": "", "permissions": []}],
            "core_modules": [{"name": "Projects", "description": "", "features": []}],
            "domain_entities": [
                {
                    "name": "Project",
                    "description": "Project entity",
                    "fields": [{"name": "id", "type": "uuid", "required": True}],
                    "relationships": [],
                }
            ],
            "pages": [
                {
                    "path": "/projects",
                    "name": "Projects",
                    "purpose": "List projects",
                    "components": [],
                    "data_dependencies": [],
                }
            ],
            "api_needs": [{"resource": "projects", "operations": ["list"], "consumers": []}],
            "business_requirement_stories": [],
            "non_functional_requirements": {},
            "assumptions": [],
            "open_questions": [],
        },
        {
            "base_path": "/api/v1",
            "resources": [
                {
                    "name": "projects",
                    "description": "Manage projects",
                    "endpoints": [
                        {
                            "method": "GET",
                            "path": "/projects",
                            "purpose": "List projects",
                        }
                    ],
                }
            ],
            "schemas": [{"name": "ProjectResponse", "fields": []}],
            "error_model": {"name": "ApiError", "fields": []},
            "notes": [],
        },
        {
            "database": {
                "engine": "PostgreSQL",
                "orm": "SQLAlchemy 2.x",
                "migration_tool": "Alembic",
            },
            "entities": [
                {
                    "name": "Project",
                    "table_name": "projects",
                    "fields": [{"name": "name", "type": "string"}],
                }
            ],
            "relationships": [],
            "indexes": [],
            "migration_notes": [],
        },
    )


def test_project_crud_flow(client: TestClient) -> None:
    first = client.post("/api/v1/projects", json={"name": "First", "description": "one"})
    second = client.post("/api/v1/projects", json={"name": "Second", "description": None})

    assert first.status_code == 201
    assert second.status_code == 201
    first_project = first.json()
    assert first_project["status"] == "draft"
    assert "Next.js" in first_project["target_frontend_stack"]

    list_response = client.get("/api/v1/projects")
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["Second", "First"]

    detail_response = client.get(f"/api/v1/projects/{first_project['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "First"

    update_response = client.patch(
        f"/api/v1/projects/{first_project['id']}",
        json={"name": "Updated", "status": "active"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated"
    assert update_response.json()["status"] == "active"

    delete_response = client.delete(f"/api/v1/projects/{first_project['id']}")
    assert delete_response.status_code == 204
    missing_response = client.get(f"/api/v1/projects/{first_project['id']}")
    assert missing_response.status_code == 404


def test_create_project_does_not_require_description(client: TestClient) -> None:
    response = client.post("/api/v1/projects", json={"name": "测试项目"})

    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "测试项目"
    assert project["description"] is None


def test_create_project_trims_name(client: TestClient) -> None:
    response = client.post("/api/v1/projects", json={"name": "  测试项目  "})

    assert response.status_code == 201
    assert response.json()["name"] == "测试项目"


def test_create_project_rejects_blank_name(client: TestClient) -> None:
    response = client.post("/api/v1/projects", json={"name": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "项目名称不能为空。"


def test_create_project_rejects_duplicate_name(client: TestClient) -> None:
    first_response = client.post("/api/v1/projects", json={"name": "测试项目"})
    second_response = client.post("/api/v1/projects", json={"name": "测试项目"})

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "项目名称已存在，请使用其他名称。"


def test_create_project_rejects_duplicate_name_after_trim(client: TestClient) -> None:
    first_response = client.post("/api/v1/projects", json={"name": "测试项目"})
    second_response = client.post("/api/v1/projects", json={"name": "  测试项目  "})

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "项目名称已存在，请使用其他名称。"


def test_update_project_rejects_duplicate_name(client: TestClient) -> None:
    first_project = client.post("/api/v1/projects", json={"name": "First"}).json()
    client.post("/api/v1/projects", json={"name": "Second"})

    response = client.patch(
        f"/api/v1/projects/{first_project['id']}",
        json={"name": " Second "},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "项目名称已存在，请使用其他名称。"


def test_update_project_rejects_blank_name(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "First"}).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "项目名称不能为空。"


def test_update_project_rejects_null_name(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "First"}).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": None},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "项目名称不能为空。"


def test_project_list_searches_name_case_insensitively(client: TestClient) -> None:
    client.post("/api/v1/projects", json={"name": "Context Planner"})
    client.post("/api/v1/projects", json={"name": "Billing Portal"})
    client.post("/api/v1/projects", json={"name": "上下文编排器"})

    match_response = client.get("/api/v1/projects?q=context")
    assert match_response.status_code == 200
    assert [item["name"] for item in match_response.json()] == ["Context Planner"]

    case_response = client.get("/api/v1/projects?q=CONTEXT")
    assert case_response.status_code == 200
    assert [item["name"] for item in case_response.json()] == ["Context Planner"]

    unicode_response = client.get("/api/v1/projects?q=上下文")
    assert unicode_response.status_code == 200
    assert [item["name"] for item in unicode_response.json()] == ["上下文编排器"]

    blank_response = client.get("/api/v1/projects?q=%20%20")
    assert blank_response.status_code == 200
    assert [item["name"] for item in blank_response.json()] == [
        "上下文编排器",
        "Billing Portal",
        "Context Planner",
    ]


def test_delete_project_removes_all_related_content(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    _patch_generation_json(monkeypatch)
    project = client.post("/api/v1/projects", json={"name": "Cascade All"}).json()
    client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "build a full context orchestration workflow"},
    )
    blueprint = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()
    api_contract = client.post(
        f"/api/v1/projects/{project['id']}/generate/api-contract"
    ).json()
    db_model = client.post(f"/api/v1/projects/{project['id']}/generate/db-model").json()
    context_packs = client.post(
        f"/api/v1/projects/{project['id']}/generate/context-packs"
    ).json()

    delete_response = client.delete(f"/api/v1/projects/{project['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/requirements").status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/blueprints").status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/api-contracts").status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/db-models").status_code == 404
    assert client.get(f"/api/v1/projects/{project['id']}/context-packs").status_code == 404
    assert client.get(f"/api/v1/blueprints/{blueprint['id']}").status_code == 404
    assert client.get(f"/api/v1/api-contracts/{api_contract['id']}").status_code == 404
    assert client.get(f"/api/v1/db-models/{db_model['id']}").status_code == 404
    assert client.get(f"/api/v1/context-packs/{context_packs[0]['id']}").status_code == 404

    for model in (
        Project,
        Requirement,
        ProjectBlueprint,
        ApiContractDraft,
        DbModelDraft,
        ContextPack,
        GenerationRun,
    ):
        assert db_session.scalars(select(model)).all() == []


def test_project_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
