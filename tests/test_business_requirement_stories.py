import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun
from tests.llm_stream_helpers import patch_llm_stream, patch_llm_stream_sequence

VALID_LLM_OUTPUT = """
{
  "stories": [
    {
      "title": "创建任务",
      "priority": "p1_must",
      "user_story": "作为已登录用户，我希望创建一项任务，以便记录需要完成的事项。",
      "business_scope": {
        "included": ["输入标题", "输入可选描述"],
        "excluded": ["子任务", "附件"]
      },
      "data_rules": [
        {"field": "title", "rule": "必填，1～100 个字符"}
      ],
      "acceptance_criteria": [
        "已登录用户可以创建合法任务。",
        "标题为空时显示校验信息。"
      ],
      "vertical_slice_note": "这是一个可独立交付的任务创建闭环。"
    },
    {
      "title": "附件管理",
      "priority": "p4_wont",
      "user_story": "作为用户，我希望给任务添加附件，以便补充背景资料。",
      "business_scope": {
        "included": ["说明为什么本阶段不做"],
        "excluded": ["上传附件", "下载附件"]
      },
      "data_rules": [],
      "acceptance_criteria": [
        "蓝图中明确附件管理不属于当前阶段。"
      ],
      "vertical_slice_note": "附件会增加存储复杂度，本阶段排除。"
    }
  ]
}
"""

VALID_LLM_OUTPUT_DICT = json.loads(VALID_LLM_OUTPUT)


def _create_project_with_requirement(client: TestClient) -> tuple[dict, dict]:
    project = client.post(
        "/api/v1/projects",
        json={"name": "Business Stories", "description": "demo"},
    ).json()
    requirement = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "做一个任务管理工具，支持创建任务，暂不支持附件。"},
    ).json()
    return project, requirement


def _create_business_stories(client: TestClient, monkeypatch) -> list[dict]:
    project, requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)
    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"]},
    )
    assert response.status_code == 201
    return response.json()["items"]


def test_generate_business_stories_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/generate/business-stories",
        json={},
    )

    assert response.status_code == 404


def test_generate_business_stories_requires_requirement(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "No Requirement"}).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 400


def test_generate_business_stories_requires_configured_llm(
    client: TestClient, db_session
) -> None:
    project, requirement = _create_project_with_requirement(client)

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 503
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"
    assert str(run.requirement_id) == requirement["id"]
    assert run.message == "业务需求故事更新失败"


def test_generate_list_update_and_read_business_stories(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)

    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"], "overwrite": False},
    )

    assert response.status_code == 201
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["status"] == "draft"
    assert payload["items"][0]["priority"] == "p1_must"
    assert payload["items"][0]["generation_run_id"] is not None

    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories",
            GenerationRun.status == "completed",
        )
    )
    assert run is not None
    assert str(run.requirement_id) == requirement["id"]
    assert run.progress == 100
    assert run.message == "业务需求故事已更新。"
    assert run.output_snapshot["story_count"] == 2

    requirements_response = client.get(f"/api/v1/projects/{project['id']}/requirements")
    assert requirements_response.status_code == 200
    generation = requirements_response.json()[0]["business_story_generation"]
    assert generation["run_id"] == str(run.id)
    assert generation["status"] == "succeeded"
    assert generation["progress"] == 100
    assert generation["message"] == "业务需求故事已更新。"

    status_response = client.get(
        f"/api/v1/requirements/{requirement['id']}/business-story-generation"
    )
    assert status_response.status_code == 200
    assert status_response.json()["run_id"] == str(run.id)

    list_response = client.get(
        f"/api/v1/projects/{project['id']}/business-stories?priority=p1_must&q=创建"
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    story_id = list_response.json()[0]["id"]
    update_response = client.patch(
        f"/api/v1/business-stories/{story_id}",
        json={"status": "ready", "priority": "p2_should", "title": "创建待办任务"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "ready"
    assert update_response.json()["priority"] == "p2_should"

    detail_response = client.get(f"/api/v1/business-stories/{story_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "创建待办任务"


def test_generate_business_stories_rejects_requirement_from_other_project(
    client: TestClient,
) -> None:
    project, _requirement = _create_project_with_requirement(client)
    other_project = client.post(
        "/api/v1/projects",
        json={"name": "Other Business Stories", "description": "demo"},
    ).json()
    other_requirement = client.post(
        f"/api/v1/projects/{other_project['id']}/requirements",
        json={"raw_text": "另一个项目的需求。"},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": other_requirement["id"]},
    )

    assert response.status_code == 400


def test_failed_business_story_generation_status_is_persisted(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)

    patch_llm_stream(monkeypatch, {"stories": [{"title": "bad"}]})

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"]},
    )

    assert response.status_code == 502
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"
    assert str(run.requirement_id) == requirement["id"]
    assert run.message == "业务需求故事更新失败"
    assert "missing required field" in (run.error_message or "")

    status_response = client.get(
        f"/api/v1/requirements/{requirement['id']}/business-story-generation"
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "failed"
    assert status_response.json()["message"] == "业务需求故事更新失败"


def test_business_story_generation_status_returns_null_without_run(
    client: TestClient,
) -> None:
    _project, requirement = _create_project_with_requirement(client)

    response = client.get(
        f"/api/v1/requirements/{requirement['id']}/business-story-generation"
    )

    assert response.status_code == 200
    assert response.json() is None


def test_patch_business_story_user_story_trims_and_preserves_unset_fields(
    client: TestClient, monkeypatch
) -> None:
    story = _create_business_stories(client, monkeypatch)[0]

    response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"user_story": "  作为用户，我希望快速创建任务。  "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_story"] == "作为用户，我希望快速创建任务。"
    assert payload["business_scope"] == story["business_scope"]
    assert payload["data_rules"] == story["data_rules"]
    assert payload["acceptance_criteria"] == story["acceptance_criteria"]
    assert payload["priority"] == story["priority"]
    assert payload["status"] == story["status"]


def test_patch_business_story_rejects_blank_user_story(
    client: TestClient, monkeypatch
) -> None:
    story = _create_business_stories(client, monkeypatch)[0]

    response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"user_story": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "用户故事不能为空。"


def test_patch_business_story_normalizes_business_scope(
    client: TestClient, monkeypatch
) -> None:
    story = _create_business_stories(client, monkeypatch)[0]

    response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"business_scope": {"included": [" 输入标题 ", "", "输入描述"]}},
    )

    assert response.status_code == 200
    assert response.json()["business_scope"] == {
        "included": ["输入标题", "输入描述"],
        "excluded": [],
    }


def test_patch_business_story_normalizes_data_rules(
    client: TestClient, monkeypatch
) -> None:
    story = _create_business_stories(client, monkeypatch)[0]

    response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={
            "data_rules": [
                {"field": " title ", "rule": " 必填 "},
                {"rule": " 不能超过 100 个字符 "},
                {"field": "description", "rule": "   "},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["data_rules"] == [
        {"rule": "必填", "field": "title"},
        {"rule": "不能超过 100 个字符"},
    ]


def test_patch_business_story_normalizes_acceptance_criteria(
    client: TestClient, monkeypatch
) -> None:
    story = _create_business_stories(client, monkeypatch)[0]

    response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"acceptance_criteria": [" 可以创建任务。 ", "", "标题为空时显示错误。"]},
    )

    assert response.status_code == 200
    assert response.json()["acceptance_criteria"] == [
        "可以创建任务。",
        "标题为空时显示错误。",
    ]


def test_patch_business_story_rejects_invalid_editable_json_fields(
    client: TestClient, monkeypatch
) -> None:
    story = _create_business_stories(client, monkeypatch)[0]

    business_scope_response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"business_scope": "bad"},
    )
    data_rules_response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"data_rules": {"rule": "bad"}},
    )
    acceptance_criteria_response = client.patch(
        f"/api/v1/business-stories/{story['id']}",
        json={"acceptance_criteria": {"text": "bad"}},
    )

    assert business_scope_response.status_code in {400, 422}
    assert data_rules_response.status_code in {400, 422}
    assert acceptance_criteria_response.status_code in {400, 422}


def test_generate_business_stories_requests_json_object_response_format(
    client: TestClient, monkeypatch
) -> None:
    project, _requirement = _create_project_with_requirement(client)
    calls = []

    def fake_stream(_self, *_args, **kwargs):
        calls.append(kwargs)
        yield json.dumps(VALID_LLM_OUTPUT_DICT, ensure_ascii=False)

    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        fake_stream,
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 201
    assert calls[0]["extra_params"] == {"response_format": {"type": "json_object"}}


def test_generate_business_stories_returns_502_for_invalid_json_output(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, _requirement = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: iter(["not json"]),
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 502
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"
    assert run.output_snapshot["failure_stage"] == "parse"


def test_generate_business_stories_validates_llm_output(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, _requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, {"stories": [{"title": "bad"}]})

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM 返回的结构化结果格式不正确，请重试或调整模型配置。"
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"


def test_generate_business_stories_fails_when_no_valid_story(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, _requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, {"stories": []})

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 502
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"
    assert run.message == "业务需求故事更新失败"
    assert run.error_message == "未生成有效业务需求故事。"
    assert db_session.scalars(select(BusinessRequirementStory)).all() == []


def test_generate_business_stories_overwrite_false_appends_existing(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)

    first = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"], "overwrite": False},
    )
    second = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"], "overwrite": False},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    stories = db_session.scalars(select(BusinessRequirementStory)).all()
    assert len(stories) == 4
    assert {str(story.requirement_id) for story in stories} == {requirement["id"]}

    list_response = client.get(f"/api/v1/projects/{project['id']}/business-stories")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 4


def test_generate_business_stories_overwrite_replaces_existing(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)

    first = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"], "overwrite": False},
    )
    second = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"], "overwrite": True},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    stories = db_session.scalars(select(BusinessRequirementStory)).all()
    assert len(stories) == 2


def test_delete_business_story_removes_single_story(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)
    generate_response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"]},
    )
    stories = generate_response.json()["items"]
    deleted_story_id = stories[0]["id"]
    remaining_story_id = stories[1]["id"]

    response = client.delete(f"/api/v1/business-stories/{deleted_story_id}")

    assert response.status_code == 204
    assert response.content == b""
    list_response = client.get(f"/api/v1/projects/{project['id']}/business-stories")
    assert list_response.status_code == 200
    listed_story_ids = {story["id"] for story in list_response.json()}
    assert deleted_story_id not in listed_story_ids
    assert remaining_story_id in listed_story_ids

    persisted_story_ids = {
        str(story.id) for story in db_session.scalars(select(BusinessRequirementStory)).all()
    }
    assert persisted_story_ids == {remaining_story_id}


def test_delete_business_story_returns_404_for_missing_story(client: TestClient) -> None:
    response = client.delete(
        "/api/v1/business-stories/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


def test_blueprint_includes_business_stories_when_available(
    client: TestClient, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    patch_llm_stream_sequence(
        monkeypatch,
        VALID_LLM_OUTPUT_DICT,
        {
            "project": {
                "name": project["name"],
                "one_liner": "任务管理",
                "target_users": ["用户"],
                "business_goal": "管理任务",
                "tech_stack": {"frontend": "Next.js", "backend": "FastAPI"},
            },
            "product_goals": [{"goal": "管理任务", "priority": "must_have"}],
            "user_roles": [{"name": "用户", "description": "", "permissions": []}],
            "core_modules": [{"name": "任务", "description": "", "features": []}],
            "domain_entities": [
                {
                    "name": "Task",
                    "description": "",
                    "fields": [{"name": "id", "type": "uuid", "required": True}],
                    "relationships": [],
                }
            ],
            "pages": [
                {
                    "path": "/tasks",
                    "name": "任务列表",
                    "purpose": "查看任务",
                    "components": [],
                    "data_dependencies": [],
                }
            ],
            "api_needs": [{"resource": "tasks", "operations": ["list"], "consumers": []}],
            "business_requirement_stories": [],
            "non_functional_requirements": {},
            "assumptions": [],
            "open_questions": [],
        },
    )
    client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"]},
    )

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 201
    blueprint = response.json()
    assert len(blueprint["content"]["business_requirement_stories"]) == 2
    assert blueprint["content"]["business_requirement_stories"][0]["title"] == "创建任务"


def test_delete_project_cascades_business_stories(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, VALID_LLM_OUTPUT_DICT)
    client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"]},
    )

    response = client.delete(f"/api/v1/projects/{project['id']}")

    assert response.status_code == 204
    assert db_session.scalars(select(BusinessRequirementStory)).all() == []
