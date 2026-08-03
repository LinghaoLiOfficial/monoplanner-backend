from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import security
from app.models.api_contract import ApiContractDraft
from app.models.backend_service_design import BackendServiceDesign
from app.models.backend_tooling import BackendTooling
from app.models.blueprint import ProjectBlueprint
from app.models.change_set import ChangeSet
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.frontend_page_structure import FrontendPageStructure
from app.models.frontend_tooling import FrontendTooling
from app.models.project import Project
from app.models.ui_design import UIDesign
from app.models.user import User
from app.models.ux_design import UXDesign


def test_project_config_read_and_patch(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Phase Config"}).json()

    detail_response = client.get(f"/api/v1/projects/{project['id']}/config")
    assert detail_response.status_code == 200
    assert detail_response.json()["global_constraints"] == []

    update_response = client.patch(
        f"/api/v1/projects/{project['id']}/config",
        json={
            "target_frontend_stack": "Next.js + Tailwind",
            "global_constraints": ["只生成结构化资产"],
            "coding_preferences": [{"style": "typed"}],
            "prompt_preferences": ["简洁"],
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["target_frontend_stack"] == "Next.js + Tailwind"
    assert payload["target_stacks_configured"] is True
    assert payload["global_constraints"] == ["只生成结构化资产"]
    assert payload["coding_preferences"] == [{"style": "typed"}]
    assert payload["prompt_preferences"] == ["简洁"]


def test_new_design_asset_modules_list_detail_and_patch(
    client: TestClient, db_session: Session
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Design Assets"}).json()
    assets = [
        (
            UXDesign,
            "/api/v1/projects/{project_id}/ux-designs",
            "/api/v1/ux-designs/{asset_id}",
            "UX 设计",
        ),
        (
            UIDesign,
            "/api/v1/projects/{project_id}/ui-designs",
            "/api/v1/ui-designs/{asset_id}",
            "UI 设计",
        ),
        (
            FrontendPageStructure,
            "/api/v1/projects/{project_id}/frontend-page-structures",
            "/api/v1/frontend-page-structures/{asset_id}",
            "页面结构",
        ),
        (
            FrontendTooling,
            "/api/v1/projects/{project_id}/frontend-toolings",
            "/api/v1/frontend-toolings/{asset_id}",
            "前端工具",
        ),
        (
            BackendServiceDesign,
            "/api/v1/projects/{project_id}/backend-service-designs",
            "/api/v1/backend-service-designs/{asset_id}",
            "后端服务",
        ),
        (
            BackendTooling,
            "/api/v1/projects/{project_id}/backend-toolings",
            "/api/v1/backend-toolings/{asset_id}",
            "后端工具",
        ),
    ]

    for model, list_path, detail_path, title in assets:
        asset = model(
            project_id=project["id"],
            version=2,
            title=title,
            summary="初版",
            content={"items": []},
            diff_from_previous={"added": []},
        )
        older_asset = model(
            project_id=project["id"],
            version=1,
            title=f"{title} older",
            summary="旧版",
            content={"items": ["old"]},
            diff_from_previous={},
        )
        db_session.add(older_asset)
        db_session.add(asset)
        db_session.commit()
        db_session.refresh(asset)

        list_response = client.get(list_path.format(project_id=project["id"]))
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == str(asset.id)
        assert list_response.json()[0]["version"] == 2
        assert list_response.json()[0]["diff_from_previous"] == {"added": []}

        detail_response = client.get(detail_path.format(asset_id=asset.id))
        assert detail_response.status_code == 200
        assert detail_response.json()["title"] == title

        patch_response = client.patch(
            detail_path.format(asset_id=asset.id),
            json={
                "title": f"{title} v2",
                "content": {"items": ["updated"]},
                "diff_from_previous": {"modified": ["items"]},
            },
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["title"] == f"{title} v2"
        assert patch_response.json()["content"] == {"items": ["updated"]}


def test_ux_ui_designs_enforce_project_ownership(
    client: TestClient, db_session: Session
) -> None:
    other_user = User(
        email="other@example.com",
        username="otheruser",
        password_hash=security.hash_password("StrongPass1!"),
        role="user",
        is_active=True,
        is_email_verified=True,
        avatar_seed=security.make_avatar_seed("otheruser"),
        avatar_bg_color=security.make_avatar_color("otheruser"),
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    other_project = Project(owner_user_id=other_user.id, name="Other Project")
    db_session.add(other_project)
    db_session.commit()
    db_session.refresh(other_project)
    ux_design = UXDesign(
        project_id=other_project.id,
        version=1,
        title="Other UX",
        content={"version_summary": "private"},
    )
    ui_design = UIDesign(
        project_id=other_project.id,
        version=1,
        title="Other UI",
        content={"version_summary": "private"},
    )
    db_session.add_all([ux_design, ui_design])
    db_session.commit()
    db_session.refresh(ux_design)
    db_session.refresh(ui_design)

    assert client.get(f"/api/v1/projects/{other_project.id}/ux-designs").status_code == 404
    assert client.get(f"/api/v1/ux-designs/{ux_design.id}").status_code == 404
    response = client.patch(f"/api/v1/ui-designs/{ui_design.id}", json={"title": "Nope"})
    assert response.status_code == 404


def test_change_sets_and_existing_asset_patch_aliases(
    client: TestClient, db_session: Session
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Compat Assets"}).json()
    blueprint = ProjectBlueprint(
        project_id=project["id"],
        version=1,
        title="项目蓝图",
        summary="初版",
        content={"project": {}},
    )
    change_set = ChangeSet(
        project_id=project["id"],
        version=1,
        title="创建任务变更",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=["api_contract"],
        content={"change": "task"},
    )
    db_session.add_all([blueprint, change_set])
    db_session.commit()
    db_session.refresh(blueprint)
    db_session.refresh(change_set)

    api_contract = ApiContractDraft(
        project_id=project["id"],
        blueprint_id=blueprint.id,
        version=1,
        title="API",
        summary="初版",
        base_path="/api/v1",
        content={"resources": []},
    )
    db_model = DbModelDraft(
        project_id=project["id"],
        blueprint_id=blueprint.id,
        version=1,
        title="DB",
        summary="初版",
        content={"entities": []},
    )
    context_pack = ContextPack(
        project_id=project["id"],
        blueprint_id=blueprint.id,
        role="backend_engineer",
        title="Prompt",
        summary="初版",
        content={"batch_summary": "demo"},
        prompt_text="Do the work",
        format="markdown",
    )
    db_session.add_all([api_contract, db_model, context_pack])
    db_session.commit()
    db_session.refresh(api_contract)
    db_session.refresh(db_model)
    db_session.refresh(context_pack)

    change_response = client.get(f"/api/v1/projects/{project['id']}/change-sets")
    assert change_response.status_code == 200
    assert change_response.json()[0]["title"] == "创建任务变更"

    apply_response = client.post(f"/api/v1/change-sets/{change_set.id}/apply")
    assert apply_response.status_code == 202
    assert apply_response.json()["run_type"] == "apply_change_set"

    blueprint_patch = client.patch(
        f"/api/v1/blueprints/{blueprint.id}",
        json={"diff_from_previous": {"modified": ["summary"]}},
    )
    assert blueprint_patch.status_code == 200
    assert blueprint_patch.json()["diff_from_previous"] == {"modified": ["summary"]}

    api_patch = client.patch(
        f"/api/v1/api-contracts/{api_contract.id}",
        json={"base_path": "/api/v2", "content": {"resources": ["tasks"]}},
    )
    assert api_patch.status_code == 200
    assert api_patch.json()["base_path"] == "/api/v2"
    assert api_patch.json()["content"] == {"resources": ["tasks"]}

    db_patch = client.patch(
        f"/api/v1/db-models/{db_model.id}",
        json={"content": {"entities": ["Task"]}},
    )
    assert db_patch.status_code == 200
    assert db_patch.json()["content"] == {"entities": ["Task"]}

    prompt_list = client.get(f"/api/v1/projects/{project['id']}/prompt-packs")
    assert prompt_list.status_code == 200
    assert prompt_list.json()[0]["id"] == str(context_pack.id)

    context_patch = client.patch(
        f"/api/v1/context-packs/{context_pack.id}",
        json={"prompt_text": "Updated prompt"},
    )
    assert context_patch.status_code == 200
    assert context_patch.json()["prompt_text"] == "Updated prompt"
