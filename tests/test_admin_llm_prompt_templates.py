from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, make_avatar_color, make_avatar_seed
from app.models.user import User
from app.services.llm_prompt_template_service import ADMIN_LLM_PROMPT_TEMPLATE_MODULES

ALLOWED_TEMPLATE_NAMES = {
    "project_description_options",
    "business_story_decomposer",
    "change_set",
    "ux_design",
    "ui_design",
    "frontend_pages",
    "api_contract",
    "backend_implementation",
    "database_models",
    "prompt_pack",
}


def test_llm_prompt_templates_require_login(
    db_session: Session,
) -> None:
    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as unauthenticated_client:
            response = unauthenticated_client.get("/api/v1/admin/llm-prompt-templates")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_llm_prompt_templates_require_admin(client: TestClient) -> None:
    response = client.get("/api/v1/admin/llm-prompt-templates")

    assert response.status_code == 403


def test_admin_can_list_new_llm_prompt_templates(db_session: Session) -> None:
    admin = User(
        email="admin@example.com",
        username="adminuser",
        password_hash=hash_password("StrongPass1!"),
        role="admin",
        is_active=True,
        is_email_verified=True,
        avatar_seed=make_avatar_seed("adminuser"),
        avatar_bg_color=make_avatar_color("adminuser"),
    )
    db_session.add(admin)
    db_session.commit()

    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as admin_client:
            login = admin_client.post(
                "/api/v1/auth/login",
                json={"email": admin.email, "password": "StrongPass1!"},
            )
            assert login.status_code == 200

            response = admin_client.get("/api/v1/admin/llm-prompt-templates")
    finally:
        app.dependency_overrides.clear()
    
    assert response.status_code == 200
    payload = response.json()
    assert [item["module_key"] for item in payload] == [
        item.module_key for item in ADMIN_LLM_PROMPT_TEMPLATE_MODULES
    ]

    template_names = {
        task["template_name"]
        for module in payload
        for task in module["tasks"]
    }
    assert template_names == ALLOWED_TEMPLATE_NAMES
    assert "blueprint_generator" not in template_names
    assert "api_contract_generator" not in template_names
    assert "db_model_generator" not in template_names
    assert "context_pack" not in template_names
    assert "design_asset" not in template_names
    assert "blueprint_summary" not in template_names

    for module in payload:
        assert module["module_label"]
        assert module["tasks"]
        for task in module["tasks"]:
            assert task["task_key"]
            assert task["task_label"]
            assert task["run_type"]
            assert task["schema_name"]
            assert task["system_prompt"]
            assert task["user_prompt_template"]
            assert "Input:" in task["user_prompt_template"]
            assert [version["language"] for version in task["versions"]] == ["zh-CN", "en"]
            for version in task["versions"]:
                assert version["system_prompt"]
                assert "Input:" in version["user_prompt_template"]
