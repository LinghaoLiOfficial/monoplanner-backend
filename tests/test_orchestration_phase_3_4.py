from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import LLMRequestError
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


def _prompt_layer(prompt_text: str) -> str | None:
    for line in prompt_text.splitlines():
        if line.startswith("layer: "):
            return line.removeprefix("layer: ").strip()
    return None


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
            "low_fidelity_screen_structure": [
                {
                    "screen_name": "任务创建页",
                    "screen_purpose": "帮助用户提交并创建任务",
                    "information_priority": ["任务标题", "提交按钮", "校验信息"],
                    "interaction_regions": [
                        {
                            "region_name": "表单区域",
                            "region_purpose": "输入任务标题和描述",
                            "content_elements": ["标题输入框", "描述输入框", "提交按钮"],
                        }
                    ],
                }
            ],
            "business_flows": [
                {
                    "flow_name": "创建任务流程",
                    "flow_goal": "让用户成功创建一条任务",
                    "primary_actor": "已登录用户",
                    "preconditions": ["用户已登录", "已进入任务创建页"],
                    "steps": [
                        {
                            "step_order": 1,
                            "involved_elements": ["标题输入框", "提交按钮"],
                            "user_action": "输入任务标题并提交",
                            "system_feedback": "显示创建中状态",
                            "branches": [
                                {
                                    "branch_status": "success",
                                    "branch_description": "任务保存成功",
                                    "system_feedback": "提示创建成功并返回任务列表",
                                },
                                {
                                    "branch_status": "error",
                                    "branch_description": "标题为空或校验失败",
                                    "system_feedback": "提示错误并允许重试",
                                },
                            ],
                        }
                    ],
                    "ux_notes": ["表单错误需可被读屏识别"],
                }
            ],
            "diff": {"added": ["task-create-flow"]},
        },
    )


def _ui_design_payload() -> dict:
    return _asset_payload(
        "UI 设计",
        {
            "version_summary": "新增任务创建视觉规则",
            "visual_system": {
                "design_style": {
                    "style_description": "清晰、工作台式、强调任务创建效率。",
                    "signature_traits": ["主操作突出", "紧凑表单", "错误就近展示"],
                },
                "design_principles": ["主操作突出", "错误状态必须有文本辅助"],
                "theme_configuration": {
                    "theme_types": {
                        "light_mode": "默认浅色主题，适合日常办公。",
                        "dark_mode": "低光环境下保持表单和状态对比度。",
                    },
                    "default_theme": "light_mode",
                },
                "color_system": ["primary 用于创建任务主按钮", "error 用于校验失败"],
                "typography_system": ["任务标题使用中等字重"],
                "spacing_system": ["表单项保持紧凑垂直间距"],
                "shape_system": ["输入框和按钮使用小圆角"],
                "elevation_system": ["表单容器不使用重阴影"],
                "interaction_visual_system": ["提交 loading 时按钮宽度保持稳定"],
            },
            "layout_rules": [
                {
                    "target_screen": "任务创建页",
                    "desktop_layout": "表单居中显示，辅助说明位于右侧",
                    "mobile_layout": "单栏表单，主按钮全宽",
                }
            ],
            "component_style_rules": [
                {
                    "component_name": "TaskForm",
                    "visual_priority": {
                        "primary_content": ["任务标题"],
                        "secondary_content": ["任务描述"],
                        "tertiary_content": ["字段帮助文本"],
                        "primary_actions": ["创建任务"],
                        "secondary_actions": ["取消"],
                        "danger_actions": [],
                    },
                    "style_rules": ["紧凑表单", "错误就近展示", "移动端主按钮全宽"],
                }
            ],
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
    assert [_prompt_layer(payload) for payload in captured_payloads[:6]] == [
        "ux_design",
        "ui_design",
        "frontend_pages",
        "api_contract",
        "backend_services",
        "database_models",
    ]
    assert '"business_flows": [' in captured_payloads[1]
    assert '"business_flows": [' in captured_payloads[2]
    assert '"visual_system": {' in captured_payloads[2]
    assert '"layout_rules": [' in captured_payloads[2]
    assert '"component_style_rules": [' in captured_payloads[2]
    assert '"new_versions":' in captured_payloads[-1]
    assert '"business_flows": [' in captured_payloads[-1]
    assert '"visual_system": {' in captured_payloads[-1]

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


def test_change_set_apply_reuses_assets_already_created_by_same_run(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="恢复中的变更集",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=["ux_design", "ui_design"],
        recommended_prompt_strategy={
            "generate_frontend_prompt": False,
            "generate_backend_prompt": False,
        },
    )
    db_session.add(change_set)
    db_session.commit()
    db_session.refresh(change_set)
    run = GenerationRun(
        project_id=project["id"],
        requirement_id=requirement["id"],
        run_type="apply_change_set",
        status="queued",
        queue_payload={
            "project_id": project["id"],
            "change_set_id": str(change_set.id),
        },
        input_snapshot={
            "project_id": project["id"],
            "change_set_id": str(change_set.id),
        },
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    existing_ux_payload = _ux_design_payload()
    existing_ux = UXDesign(
        project_id=project["id"],
        version=1,
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        change_set_id=change_set.id,
        generation_run_id=run.id,
        title=existing_ux_payload["title"],
        summary=existing_ux_payload["summary"],
        content=existing_ux_payload["content"],
        diff_from_previous=existing_ux_payload["diff_from_previous"],
    )
    db_session.add(existing_ux)
    db_session.commit()
    captured_payloads: list[dict] = []
    mocked_outputs = [_ui_design_payload(), _blueprint_summary_payload()]

    def stream(_self, _system_prompt, user_payload, **_kwargs):
        captured_payloads.append(user_payload)
        if not mocked_outputs:
            raise AssertionError("No mocked LLM stream payload remaining.")
        return stream_json_payload(mocked_outputs.pop(0))

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", stream)

    result = run_generation_job_in_new_session(run.id)

    assert result.status == "completed"
    db_session.expire_all()
    assert len(db_session.scalars(select(UXDesign)).all()) == 1
    assert len(db_session.scalars(select(UIDesign)).all()) == 1
    assert len(db_session.scalars(select(ProjectBlueprint)).all()) == 1
    assert [_prompt_layer(payload) for payload in captured_payloads] == ["ui_design", None]
    assert f'"id": "{existing_ux.id}"' in captured_payloads[0]


def test_change_set_apply_reuses_assets_created_by_previous_failed_run(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="失败后重试的变更集",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=["ux_design", "ui_design"],
        recommended_prompt_strategy={
            "generate_frontend_prompt": False,
            "generate_backend_prompt": False,
        },
    )
    failed_run = GenerationRun(
        project_id=project["id"],
        requirement_id=requirement["id"],
        run_type="apply_change_set",
        status="failed",
        queue_payload={
            "project_id": project["id"],
            "change_set_id": str(change_set.id),
        },
        input_snapshot={
            "project_id": project["id"],
            "change_set_id": str(change_set.id),
        },
    )
    db_session.add_all([change_set, failed_run])
    db_session.commit()
    db_session.refresh(change_set)
    db_session.refresh(failed_run)
    existing_ux_payload = _ux_design_payload()
    existing_ux = UXDesign(
        project_id=project["id"],
        version=1,
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        change_set_id=change_set.id,
        generation_run_id=failed_run.id,
        title=existing_ux_payload["title"],
        summary=existing_ux_payload["summary"],
        content=existing_ux_payload["content"],
        diff_from_previous=existing_ux_payload["diff_from_previous"],
    )
    db_session.add(existing_ux)
    db_session.commit()
    captured_payloads: list[dict] = []
    mocked_outputs = [_ui_design_payload(), _blueprint_summary_payload()]

    def stream(_self, _system_prompt, user_payload, **_kwargs):
        captured_payloads.append(user_payload)
        if not mocked_outputs:
            raise AssertionError("No mocked LLM stream payload remaining.")
        return stream_json_payload(mocked_outputs.pop(0))

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", stream)

    response = client.post(f"/api/v1/change-sets/{change_set.id}/apply")

    assert response.status_code == 202
    result = run_generation_job_in_new_session(response.json()["id"])
    assert result.status == "completed"
    db_session.expire_all()
    ux_assets = db_session.scalars(select(UXDesign)).all()
    assert len(ux_assets) == 1
    assert ux_assets[0].generation_run_id == failed_run.id
    assert len(db_session.scalars(select(UIDesign)).all()) == 1
    assert [_prompt_layer(payload) for payload in captured_payloads] == ["ui_design", None]
    assert f'"id": "{existing_ux.id}"' in captured_payloads[0]


def test_change_set_apply_llm_request_error_is_requeued(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project, requirement, story = _create_project_requirement_and_story(client, db_session)
    change_set = ChangeSet(
        project_id=project["id"],
        source_requirement_id=requirement["id"],
        source_story_id=story.id,
        version=1,
        title="临时失败的变更集",
        status="ready",
        implementation_scope="fullstack",
        affected_layers=["ux_design"],
        recommended_prompt_strategy={
            "generate_frontend_prompt": False,
            "generate_backend_prompt": False,
        },
    )
    db_session.add(change_set)
    db_session.commit()
    db_session.refresh(change_set)

    def fail_stream(*_args, **_kwargs):
        raise LLMRequestError("temporary upstream stream failure")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_stream)

    response = client.post(f"/api/v1/change-sets/{change_set.id}/apply")

    assert response.status_code == 202
    result = run_generation_job_in_new_session(response.json()["id"])
    assert result.status == "queued"
    assert result.attempt_count == 1
    assert result.next_attempt_at is not None
    db_session.expire_all()
    assert db_session.scalars(select(UXDesign)).all() == []


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
