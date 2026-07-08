from fastapi.testclient import TestClient


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

    list_response = client.get(f"/api/v1/projects/{project['id']}/requirements")
    assert list_response.status_code == 200
    assert [item["raw_text"] for item in list_response.json()] == [
        "second requirement",
        "first requirement",
    ]


def test_create_requirement_for_missing_project_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000001/requirements",
        json={"raw_text": "missing"},
    )

    assert response.status_code == 404
