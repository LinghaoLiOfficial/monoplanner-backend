from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_verification_code
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.services.auth_service import AuthService


def test_settings_accepts_qq_smtp_verification_config() -> None:
    from app.core.config import Settings

    settings = Settings(
        SMTP_HOST="smtp.qq.com",
        SMTP_PORT=465,
        SMTP_CODE="qq-mail-auth-code",
        SMTP_SENDER_EMAIL="sender@qq.com",
    )

    assert settings.smtp_configured is True
    assert settings.smtp_host == "smtp.qq.com"
    assert settings.smtp_port == 465
    assert settings.smtp_code == "qq-mail-auth-code"
    assert settings.smtp_sender_email == "sender@qq.com"
    assert settings.smtp_login_username == "sender@qq.com"


def test_login_sets_cookie_and_me_returns_safe_user(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "testuser"
    assert "password_hash" not in payload
    assert "access_token" not in payload


def test_login_accepts_email_and_sets_cookie(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    assert "access_token" in response.cookies
    payload = response.json()["user"]
    assert payload["email"] == "test@example.com"
    assert payload["username"] == "testuser"


def test_login_rejects_username_payload(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "StrongPass1!"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "missing@example.com", "password": "StrongPass1!"},
        {"email": "test@example.com", "password": "WrongPass1!"},
    ],
)
def test_login_rejects_unknown_email_or_wrong_password(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    response = client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "邮箱或密码错误。"


def test_login_normalizes_email_case(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  TEST@EXAMPLE.COM  ", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "test@example.com"


def test_login_rejects_inactive_user(db_session: Session, client: TestClient) -> None:
    disabled_user = User(
        email="disabled@example.com",
        username="disableduser",
        password_hash=hash_password("StrongPass1!"),
        role="user",
        is_active=False,
        is_email_verified=True,
        avatar_seed="D",
        avatar_bg_color="#2563eb",
    )
    db_session.add(disabled_user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "StrongPass1!"},
    )

    assert response.status_code == 403


def test_login_openapi_schema_uses_email_not_username(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    login_schema_ref = schema["paths"]["/api/v1/auth/login"]["post"]["requestBody"][
        "content"
    ]["application/json"]["schema"]["$ref"]
    login_schema_name = login_schema_ref.rsplit("/", 1)[-1]
    login_schema = schema["components"]["schemas"][login_schema_name]

    assert set(login_schema["properties"]) == {"email", "password"}
    assert "email" in login_schema["required"]
    assert "password" in login_schema["required"]
    assert "username" not in login_schema["properties"]


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


def test_register_code_alias_sends_email_verification_code(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_codes: list[tuple[str, str]] = []

    def fake_send_email_code(self: AuthService, email: str, code: str) -> None:
        sent_codes.append((email, code))

    monkeypatch.setattr(AuthService, "_send_email_code", fake_send_email_code)

    response = client.post(
        "/api/v1/auth/register/code",
        json={"email": "AliasUser@Example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "验证码已发送。"
    assert sent_codes
    assert sent_codes[0][0] == "aliasuser@example.com"


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
