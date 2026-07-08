from fastapi.testclient import TestClient


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


def test_project_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
