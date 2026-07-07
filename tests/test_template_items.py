from fastapi.testclient import TestClient


def test_create_and_list_template_items(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/template-items/",
        json={
            "key": "template-item",
            "title": "Template Item",
            "description": "Neutral scaffold example resource.",
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["data"]["key"] == "template-item"

    list_response = client.get("/api/v1/template-items/?page=1&page_size=10")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["pagination"]["total"] == 1
    assert len(list_response.json()["data"]["items"]) == 1


def test_create_template_item_rejects_duplicate_key(client: TestClient) -> None:
    payload = {
        "key": "duplicate-template",
        "title": "Duplicate Template",
        "description": "Should fail on duplicate key.",
    }

    first_response = client.post("/api/v1/template-items/", json=payload)
    second_response = client.post("/api/v1/template-items/", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "CONFLICT"
