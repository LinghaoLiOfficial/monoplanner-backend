from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun

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
    project, _requirement = _create_project_with_requirement(client)

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


def test_generate_list_update_and_read_business_stories(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)

    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.invoke",
        lambda *_args, **_kwargs: VALID_LLM_OUTPUT,
    )

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
    assert run.output_snapshot["story_count"] == 2

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


def test_generate_business_stories_validates_llm_output(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, _requirement = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.invoke",
        lambda *_args, **_kwargs: '{"stories":[{"title":"bad"}]}',
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM 返回的业务需求故事格式不正确，请重试。"
    run = db_session.scalar(
        select(GenerationRun).where(
            GenerationRun.run_type == "generate_business_requirement_stories"
        )
    )
    assert run is not None
    assert run.status == "failed"


def test_generate_business_stories_overwrite_replaces_existing(
    client: TestClient, db_session, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.invoke",
        lambda *_args, **_kwargs: VALID_LLM_OUTPUT,
    )

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


def test_blueprint_includes_business_stories_when_available(
    client: TestClient, monkeypatch
) -> None:
    project, requirement = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.invoke",
        lambda *_args, **_kwargs: VALID_LLM_OUTPUT,
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
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.invoke",
        lambda *_args, **_kwargs: VALID_LLM_OUTPUT,
    )
    client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": requirement["id"]},
    )

    response = client.delete(f"/api/v1/projects/{project['id']}")

    assert response.status_code == 204
    assert db_session.scalars(select(BusinessRequirementStory)).all() == []
