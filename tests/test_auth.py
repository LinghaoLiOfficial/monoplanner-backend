from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_verification_code
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User


def test_login_sets_cookie_and_me_returns_safe_user(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "testuser"
    assert "password_hash" not in payload
    assert "access_token" not in payload


def test_unauthenticated_project_request_returns_401(
    db_session: Session,
    test_user: User,
) -> None:
    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as unauthenticated_client:
            response = unauthenticated_client.get("/api/v1/projects")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_register_consumes_email_verification_code(db_session: Session, client: TestClient) -> None:
    email = "new@example.com"
    code = "123456"
    db_session.add(
        EmailVerificationCode(
            email=email,
            code_hash=hash_verification_code(email, code),
            purpose="register",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": "newuser",
            "password": "StrongPass1!",
            "verification_code": code,
        },
    )

    assert response.status_code == 201
    payload = response.json()["user"]
    assert payload["email"] == email
    assert payload["is_email_verified"] is True
    assert db_session.query(User).filter(User.username == "newuser").one().password_hash


def test_register_rejects_weak_password(db_session: Session, client: TestClient) -> None:
    email = "weak@example.com"
    code = "123456"
    db_session.add(
        EmailVerificationCode(
            email=email,
            code_hash=hash_verification_code(email, code),
            purpose="register",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": "weakuser",
            "password": "password",
            "verification_code": code,
        },
    )

    assert response.status_code == 400
