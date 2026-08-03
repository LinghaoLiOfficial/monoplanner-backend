from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_contract import ApiContractDraft
from app.models.backend_service_design import BackendServiceDesign
from app.models.blueprint import ProjectBlueprint
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.frontend_page_structure import FrontendPageStructure
from app.models.generation_run import GenerationRun
from app.models.ui_design import UIDesign
from app.models.ux_design import UXDesign
from tests.llm_stream_helpers import patch_llm_stream, stream_json_payload
from tests.queue_helpers import run_generation_job_in_new_session


def _create_project_requirement_and_story(
    client: TestClient,
    db_session: Session,
) -> tuple[dict, dict, BusinessRequirementStory]:
    project = client.post("/api/v1/projects", json={"name": "Phase 3 Project"}).json()
    requirement = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "实现任务创建闭环"},
    ).json()
    story = BusinessRequirementStory(
        project_id=project["id"],
        requirement_id=requirement["id"],
        title="创建任务",
        priority="p1_must",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=[
            "ux_design",
            "ui_design",
            "frontend_pages",
            "api_contract",
            "backend_services",
            "database_models",
        ],
        user_story="作为用户，我希望创建任务。",
        business_scope={"included": ["创建任务"], "excluded": []},
        data_rules=[{"field": "title", "rule": "必填"}],
        acceptance_criteria=["可以创建任务"],
        depends_on=[],
        source_requirement_ids=[requirement["id"]],
        sort_order=1,
    )
    db_session.add(story)
    db_session.commit()
    db_session.refresh(story)
    return project, requirement, story


def _change_set_payload(*, layers: list[str] | None = None) -> dict:
    return {
        "title": "创建任务变更集",
        "status": "ready",
        "implementation_scope": "fullstack",
        "affected_layers": layers
        or [
            "ux_design",
            "ui_design",
            "frontend_pages",
            "api_contract",
            "backend_services",
            "database_models",
            "prompt_assets",
        ],
        "impact_summary": "实现任务创建闭环。",
        "module_changes": {
            "ux_design": {"added": [{"target": "任务创建流程"}]},
            "ui_design": {"added": [{"target": "任务创建表单"}]},
            "api_contract": {"added": ["POST /tasks"]},
        },
        "risks": [],
        "open_questions": [],
        "recommended_prompt_strategy": {
            "generate_frontend_prompt": True,
            "generate_backend_prompt": True,
        },
        "content": {"story": "task create"},
        "diff": {"added": ["task create"]},
    }


def _asset_payload(title: str, content: dict | None = None) -> dict:
    return {
        "title": title,
        "summary": f"{title} 更新",
        "content": content or {"version_summary": f"{title} 更新", "diff": {"added": [title]}},
        "diff_from_previous": {"added": [title]},
    }


def _ux_design_payload() -> dict:
    return _asset_payload(
        "UX 设计",
        {
            "version_summary": "新增任务创建体验",
            "user_goals": [
                {
                    "goal_id": "create-task",
                    "description": "用户可以完成任务创建",
                    "related_story_ids": [],
                }
            ],
            "user_flows": [
                {
                    "flow_id": "task-create-flow",
                    "name": "创建任务",
                    "entry_point": "任务页",
                    "steps": [
                        {
                            "step": 1,
                            "user_action": "提交任务标题",
                            "system_feedback": "显示创建中状态",
                        }
                    ],
                    "success_outcome": "任务创建成功",
                    "failure_outcome": "提示错误并允许重试",
                }
            ],
            "interaction_states": [{"state": "loading", "description": "提交中"}],
            "empty_states": [],
            "error_states": [],
            "permission_experience": [],
            "accessibility_requirements": ["表单错误需可被读屏识别"],
            "diff": {"added": ["task-create-flow"]},
        },
    )


def _ui_design_payload() -> dict:
    return _asset_payload(
        "UI 设计",
        {
            "version_summary": "新增任务创建视觉规则",
            "visual_hierarchy": [{"target": "任务创建表单", "rule": "主按钮突出"}],
            "layout_guidelines": [
                {"target": "任务页", "desktop": "双栏", "mobile": "单栏"}
            ],
            "component_style_rules": [{"component": "TaskForm", "rules": ["紧凑表单"]}],
            "badge_rules": [],
            "button_rules": [
                {"button": "create-task", "priority": "primary", "states": ["loading"]}
            ],
            "form_rules": [{"target": "TaskForm", "rules": ["错误就近展示"]}],
            "responsive_rules": ["移动端主按钮全宽"],
            "accessibility_visual_rules": ["错误色需有文本辅助"],
            "diff": {"added": ["TaskForm rules"]},
        },
    )


def _frontend_pages_payload() -> dict:
    return _asset_payload(
        "前端页面结构",
        {
            "version_summary": "新增任务页面结构",
            "pages": [{"route_path": "/tasks", "name": "任务页"}],
            "components": [
                {
                    "component_id": "task-form",
                    "name": "TaskForm",
                    "purpose": "创建任务",
                    "used_by_pages": ["/tasks"],
                    "ux_refs": ["task-create-flow"],
                    "ui_refs": ["TaskForm rules"],
                }
            ],
            "directory_structure": ["app/tasks/page.tsx"],
            "data_flow": ["TaskForm -> POST /tasks"],
            "diff": {"added": ["task-form"]},
        },
    )


def _blueprint_summary_payload() -> dict:
    return {
        "project": {"name": "Phase 3 Project"},
        "current_product_scope": {"included": ["创建任务"]},
        "business_capabilities": ["任务创建"],
        "ux_summary": {
            "core_user_flows": ["创建任务"],
            "key_interaction_principles": ["提交时显示清晰状态"],
        },
        "ui_summary": {
            "design_principles": ["主操作突出"],
            "component_language": ["紧凑表单"],
        },
        "frontend_summary": {"pages": ["任务页"]},
        "backend_summary": {"services": ["TaskService"]},
        "architecture_notes": ["保持分层"],
        "risks": [],
        "open_questions": [],
        "version_summary": "蓝图已聚合任务创建变更。",
    }


def _prompt_pack_payload() -> dict:
    return {
        "batch_summary": "任务创建实现指令",
        "implementation_scope": "fullstack",
        "frontend_prompt": {
            "needed": True,
            "title": "前端任务创建",
            "prompt": "实现任务创建页面。",
            "affected_files": ["app/tasks/page.tsx"],
            "do_not_modify": [],
            "verification_steps": ["运行前端测试"],
        },
        "backend_prompt": {
            "needed": True,
            "title": "后端任务创建",
            "prompt": "实现任务创建 API。",
            "affected_files": ["app/api/v1/endpoints/tasks.py"],
            "do_not_modify": [],
            "verification_steps": ["运行后端测试"],
        },
        "diff_summary": {
            "ux_design": {"added": ["任务创建流程"]},
            "ui_design": {"added": ["任务创建表单视觉规则"]},
            "frontend_pages": {"added": ["任务页"]},
        },
        "execution_order": ["backend", "frontend"],
        "acceptance_checklist": ["可以创建任务"],
        "rollback_notes": [],
    }


def test_story_execute_generates_change_set(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    _project, _requirement, story = _create_project_requirement_and_story(client, db_session)
    patch_llm_stream(monkeypatch, _change_set_payload())

    response = client.post(f"/api/v1/business-stories/{story.id}/execute")

    assert response.status_code == 202
    assert response.json()["run_type"] == "generate_change_set"
    run = run_generation_job_in_new_session(response.json()["id"])
    assert run.status == "completed"

    db_session.expire_all()
    change_set = db_session.scalar(select(ChangeSet))
    assert change_set is not None
    assert change_set.title == "创建任务变更集"
    assert change_set.source_story_id == story.id
    assert change_set.status == "ready"
    assert "ux_design" in change_set.affected_layers
    assert "ui_design" in change_set.affected_layers
    assert change_set.module_changes["ux_design"]["added"]


def test_change_set_apply_generates_assets_blueprint_and_prompt_pack(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="创建任务变更集",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=[
            "database_models",
            "frontend_pages",
            "ui_design",
            "api_contract",
            "backend_services",
            "ux_design",
            "prompt_assets",
        ],
        module_changes={
            "ux_design": {"added": ["任务创建流程"]},
            "ui_design": {"added": ["任务创建表单规则"]},
            "frontend_pages": {"added": ["任务页"]},
            "api_contract": {"added": ["POST /tasks"]},
        },
        recommended_prompt_strategy={
            "generate_frontend_prompt": True,
            "generate_backend_prompt": True,
        },
        content={"story": "task create"},
    )
    db_session.add(change_set)
    db_session.commit()
    db_session.refresh(change_set)
    captured_payloads: list[dict] = []
    mocked_outputs = [
        _ux_design_payload(),
        _ui_design_payload(),
        _frontend_pages_payload(),
        _asset_payload(
            "API 契约",
            {
                "base_path": "/api/v1",
                "resources": [],
                "schemas": [],
                "error_model": {},
                "diff": {"added": ["tasks"]},
            },
        ),
        _asset_payload("后端服务设计"),
        _asset_payload(
            "数据库模型",
            {"database": {}, "entities": [], "indexes": [], "migration_notes": [], "diff": {}},
        ),
        _blueprint_summary_payload(),
        _prompt_pack_payload(),
    ]

    def stream(_self, _system_prompt, user_payload, **_kwargs):
        captured_payloads.append(user_payload)
        if not mocked_outputs:
            raise AssertionError("No mocked LLM stream payload remaining.")
        return stream_json_payload(mocked_outputs.pop(0))

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", stream)

    response = client.post(f"/api/v1/change-sets/{change_set.id}/apply")

    assert response.status_code == 202
    run = run_generation_job_in_new_session(response.json()["id"])
    assert run.status == "completed"
    assert run.output_snapshot["change_set_id"] == str(change_set.id)
    assert [payload.get("layer") for payload in captured_payloads[:6]] == [
        "ux_design",
        "ui_design",
        "frontend_pages",
        "api_contract",
        "backend_services",
        "database_models",
    ]
    assert captured_payloads[1]["related_assets"]["ux_design"]["content"]["user_flows"]
    assert captured_payloads[2]["related_assets"]["ux_design"]["content"]["user_flows"]
    assert captured_payloads[2]["related_assets"]["ui_design"]["content"]["visual_hierarchy"]
    assert captured_payloads[-1]["new_versions"]["ux_design"]["content"]["user_flows"]
    assert captured_payloads[-1]["new_versions"]["ui_design"]["content"]["visual_hierarchy"]

    db_session.expire_all()
    refreshed_change_set = db_session.get(ChangeSet, change_set.id)
    assert refreshed_change_set.status == "applied"
    assert len(db_session.scalars(select(UXDesign)).all()) == 1
    assert len(db_session.scalars(select(UIDesign)).all()) == 1
    assert len(db_session.scalars(select(FrontendPageStructure)).all()) == 1
    assert len(db_session.scalars(select(ApiContractDraft)).all()) == 1
    assert len(db_session.scalars(select(BackendServiceDesign)).all()) == 1
    assert len(db_session.scalars(select(DbModelDraft)).all()) == 1
    assert len(db_session.scalars(select(ProjectBlueprint)).all()) == 1
    blueprint = db_session.scalar(select(ProjectBlueprint))
    assert blueprint.content["ux_summary"]["core_user_flows"] == ["创建任务"]
    assert blueprint.content["ui_summary"]["design_principles"] == ["主操作突出"]
    prompt_pack = db_session.scalar(select(ContextPack).where(ContextPack.role == "prompt_pack"))
    assert prompt_pack is not None
    assert prompt_pack.change_set_id == change_set.id
    assert "UX/UI 差异" in prompt_pack.prompt_text
    assert "ux_design" in prompt_pack.prompt_text


def test_change_set_apply_rejects_applied_status(
    client: TestClient, db_session: Session
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="已应用",
        status="applied",
        implementation_scope="fullstack",
        affected_layers=["frontend_pages"],
    )
    db_session.add(change_set)
    db_session.commit()
    db_session.refresh(change_set)

    response = client.post(f"/api/v1/change-sets/{change_set.id}/apply")

    assert response.status_code == 409
    assert db_session.scalars(select(GenerationRun)).all() == []


def test_regenerate_change_set_creates_new_record(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    old_change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="旧变更集",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=["frontend_pages"],
    )
    db_session.add(old_change_set)
    db_session.commit()
    db_session.refresh(old_change_set)
    patch_llm_stream(monkeypatch, _change_set_payload(layers=["frontend_pages"]))

    response = client.post(f"/api/v1/change-sets/{old_change_set.id}/regenerate")

    assert response.status_code == 202
    run_generation_job_in_new_session(response.json()["id"])
    db_session.expire_all()
    change_sets = db_session.scalars(select(ChangeSet).order_by(ChangeSet.version.asc())).all()
    assert len(change_sets) == 2
    assert change_sets[0].title == "旧变更集"
    assert change_sets[1].title == "创建任务变更集"


def test_prompt_pack_generate_only_creates_context_pack(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="创建任务变更集",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=["prompt_assets"],
    )
    db_session.add(change_set)
    db_session.commit()
    db_session.refresh(change_set)
    patch_llm_stream(monkeypatch, _prompt_pack_payload())

    response = client.post(
        f"/api/v1/projects/{project['id']}/prompt-packs/generate",
        json={"change_set_id": str(change_set.id)},
    )

    assert response.status_code == 202
    run = run_generation_job_in_new_session(response.json()["id"])
    assert run.status == "completed"
    assert run.output_snapshot["context_pack_ids"]
    db_session.expire_all()
    assert len(db_session.scalars(select(ContextPack)).all()) == 1
    assert len(db_session.scalars(select(FrontendPageStructure)).all()) == 0
