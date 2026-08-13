from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.models.api_contract import ApiContractDraft
from app.models.blueprint import ProjectBlueprint
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.models.project import Project
from app.models.requirement import Requirement
from tests.llm_stream_helpers import patch_llm_stream_sequence
from tests.queue_helpers import run_generation_job_in_new_session


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
            "non_functional_requirements": {
                "auth": "Cookie/JWT 登录",
                "performance": "常规页面响应",
                "security": "用户只能访问自己的项目",
                "observability": "记录生成任务状态",
            },
            "assumptions": [],
            "open_questions": [],
        },
        {
            "api_base_path": "/api/v1",
            "api_resource_groups": [
                {
                    "group_name": "projects",
                    "group_purpose": "Manage projects",
                    "endpoints": [
                        {
                            "http_method": "GET",
                            "endpoint_path": "/projects",
                            "endpoint_purpose": "List projects",
                            "requires_auth": True,
                            "request_schema": {},
                            "response_schema": {"body": "ProjectResponse"},
                            "error_model": [],
                        }
                    ],
                }
            ],
            "notes": [],
        },
        {
            "database": {
                "engine": "PostgreSQL",
                "orm": "SQLAlchemy 2.x",
                "migration_tool": "Alembic",
            },
            "database_tables": [
                {
                    "name": "Project",
                    "table_name": "projects",
                    "description": "Project table",
                    "fields": [
                        {
                            "name": "id",
                            "type": "uuid",
                            "required": True,
                            "primary_key": True,
                            "nullable": False,
                            "description": "Primary key",
                        },
                        {
                            "name": "name",
                            "type": "string",
                            "required": True,
                            "primary_key": False,
                            "nullable": False,
                            "description": "Project name",
                        },
                    ],
                    "relationships": [],
                    "indexes": [],
                    "migration_notes": [],
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
    assert project["target_stacks_configured"] is False


def test_create_project_uses_default_target_stacks(client: TestClient) -> None:
    response = client.post("/api/v1/projects", json={"name": "Default Stacks"})

    assert response.status_code == 201
    project = response.json()
    assert project["target_frontend_stack"] == DEFAULT_FRONTEND_STACK
    assert project["target_backend_stack"] == DEFAULT_BACKEND_STACK
    assert project["target_stacks_configured"] is False


def test_create_project_ignores_custom_target_stacks_until_saved(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Custom Stacks",
            "target_frontend_stack": "Remix + React",
            "target_backend_stack": "Django + PostgreSQL",
        },
    )

    assert response.status_code == 201
    project = response.json()
    assert project["target_frontend_stack"] == DEFAULT_FRONTEND_STACK
    assert project["target_backend_stack"] == DEFAULT_BACKEND_STACK
    assert project["target_stacks_configured"] is False


def test_create_project_resets_blank_target_stacks_to_defaults(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Blank Stacks",
            "target_frontend_stack": "   ",
            "target_backend_stack": "",
        },
    )

    assert response.status_code == 201
    project = response.json()
    assert project["target_frontend_stack"] == DEFAULT_FRONTEND_STACK
    assert project["target_backend_stack"] == DEFAULT_BACKEND_STACK
    assert project["target_stacks_configured"] is False


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


def test_update_project_accepts_target_stacks(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Stack Update"}).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "target_frontend_stack": "Vue + Vite",
            "target_backend_stack": "Go + Gin",
        },
    )

    assert response.status_code == 200
    updated_project = response.json()
    assert updated_project["target_frontend_stack"] == "Vue + Vite"
    assert updated_project["target_backend_stack"] == "Go + Gin"
    assert updated_project["target_stacks_configured"] is True


def test_update_project_accepts_partial_target_stack_and_marks_configured(
    client: TestClient,
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Partial Stack Update"}).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"target_frontend_stack": "Vue + Vite"},
    )

    assert response.status_code == 200
    updated_project = response.json()
    assert updated_project["target_frontend_stack"] == "Vue + Vite"
    assert updated_project["target_backend_stack"] == DEFAULT_BACKEND_STACK
    assert updated_project["target_stacks_configured"] is True


def test_update_project_preserves_target_stacks_when_unset(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Preserve Stacks"}).json()
    project = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "target_frontend_stack": "SvelteKit",
            "target_backend_stack": "Litestar",
        },
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "updated"},
    )

    assert response.status_code == 200
    updated_project = response.json()
    assert updated_project["description"] == "updated"
    assert updated_project["target_frontend_stack"] == "SvelteKit"
    assert updated_project["target_backend_stack"] == "Litestar"
    assert updated_project["target_stacks_configured"] is True


def test_update_project_resets_blank_target_stacks_to_defaults(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "Reset Stacks",
            "target_frontend_stack": "Angular",
            "target_backend_stack": "Rails",
        },
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "target_frontend_stack": " ",
            "target_backend_stack": "",
        },
    )

    assert response.status_code == 200
    updated_project = response.json()
    assert updated_project["target_frontend_stack"] == DEFAULT_FRONTEND_STACK
    assert updated_project["target_backend_stack"] == DEFAULT_BACKEND_STACK
    assert updated_project["target_stacks_configured"] is True


def test_project_response_defaults_blank_target_stacks(
    client: TestClient,
    db_session,
    test_user,
) -> None:
    project = Project(
        owner_user_id=test_user.id,
        name="Blank Stored Stacks",
        target_frontend_stack="",
        target_backend_stack="   ",
    )
    db_session.add(project)
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project.id}")

    assert response.status_code == 200
    project_response = response.json()
    assert project_response["target_frontend_stack"] == DEFAULT_FRONTEND_STACK
    assert project_response["target_backend_stack"] == DEFAULT_BACKEND_STACK


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
    blueprint_run = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()
    run_generation_job_in_new_session(blueprint_run["id"])
    blueprint = client.get(f"/api/v1/projects/{project['id']}/blueprints").json()[0]
    api_run = client.post(
        f"/api/v1/projects/{project['id']}/generate/api-contract"
    ).json()
    run_generation_job_in_new_session(api_run["id"])
    api_contract = client.get(f"/api/v1/projects/{project['id']}/api-contracts").json()[0]
    db_run = client.post(f"/api/v1/projects/{project['id']}/generate/db-model").json()
    run_generation_job_in_new_session(db_run["id"])
    db_model = client.get(f"/api/v1/projects/{project['id']}/db-models").json()[0]
    pack_run = client.post(
        f"/api/v1/projects/{project['id']}/generate/context-packs"
    ).json()
    run_generation_job_in_new_session(pack_run["id"])
    context_packs = client.get(f"/api/v1/projects/{project['id']}/context-packs").json()

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
