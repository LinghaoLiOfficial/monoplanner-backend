from fastapi.testclient import TestClient


def test_auth_placeholder_returns_standard_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo", "password": "demo"},
    )

    assert response.status_code == 501
    assert response.json()["code"] == "AUTH_NOT_IMPLEMENTED"
