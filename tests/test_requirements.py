from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.generation_run import GenerationRun
from app.services.requirement_service import BUSINESS_STORY_RUN_TYPE

VALID_PROGRESS_STATUSES = {"in_progress", "success", "failed"}
EXPECTED_DEFAULT_PROGRESS = {
    "progress_status": "success",
    "progress_label": "成功",
    "progress_text": "更新成功",
}


def test_create_and_list_project_requirements(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Req Project"}).json()

    first = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "first requirement", "language": "zh-CN", "source_type": "manual"},
    )
    second = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "second requirement"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["language"] == "zh-CN"
    assert second.json()["source_type"] == "manual"
    assert _progress_payload(first.json()) == EXPECTED_DEFAULT_PROGRESS
    assert _progress_payload(second.json()) == EXPECTED_DEFAULT_PROGRESS

    list_response = client.get(f"/api/v1/projects/{project['id']}/requirements")
    assert list_response.status_code == 200
    items = list_response.json()
    assert [item["raw_text"] for item in items] == [
        "second requirement",
        "first requirement",
    ]
    for item in items:
        assert _progress_payload(item) == EXPECTED_DEFAULT_PROGRESS
        assert item["progress_status"] in VALID_PROGRESS_STATUSES
        assert not item["progress_text"].endswith("。")


def test_create_requirement_for_missing_project_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000001/requirements",
        json={"raw_text": "missing"},
    )

    assert response.status_code == 404


def test_requirement_progress_status_maps_business_story_runs(
    client: TestClient, db_session: Session
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Progress Project"}).json()
    cases = [
        ("pending", "in_progress", "进行中", "正在更新"),
        ("queued", "in_progress", "进行中", "正在更新"),
        ("running", "in_progress", "进行中", "正在更新"),
        ("processing", "in_progress", "进行中", "正在更新"),
        ("completed", "success", "成功", "更新成功"),
        ("succeeded", "success", "成功", "更新成功"),
        ("success", "success", "成功", "更新成功"),
        ("failed", "failed", "失败", "更新失败"),
        ("error", "failed", "失败", "更新失败"),
        ("cancelled", "failed", "失败", "更新失败"),
    ]

    for run_status, *_expected in cases:
        requirement = client.post(
            f"/api/v1/projects/{project['id']}/requirements",
            json={"raw_text": f"{run_status} requirement"},
        ).json()
        db_session.add(
            GenerationRun(
                project_id=project["id"],
                requirement_id=requirement["id"],
                run_type=BUSINESS_STORY_RUN_TYPE,
                status=run_status,
                progress=100 if run_status in {"completed", "succeeded", "success"} else 10,
                message=f"{run_status} message",
            )
        )
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project['id']}/requirements")

    assert response.status_code == 200
    by_raw_text = {item["raw_text"]: item for item in response.json()}
    for run_status, progress_status, progress_label, progress_text in cases:
        item = by_raw_text[f"{run_status} requirement"]
        assert item["progress_status"] == progress_status
        assert item["progress_label"] == progress_label
        assert item["progress_text"] == progress_text
        assert item["progress_status"] in VALID_PROGRESS_STATUSES
        assert not item["progress_text"].endswith("。")


def _progress_payload(payload: dict) -> dict[str, str]:
    return {
        "progress_status": payload["progress_status"],
        "progress_label": payload["progress_label"],
        "progress_text": payload["progress_text"],
    }
