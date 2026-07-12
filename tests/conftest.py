import importlib
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://llh@localhost:5432/context_orchestrator_test",
)


def _ensure_safe_test_database_url(database_url: str) -> None:
    url = make_url(database_url)
    if not url.get_backend_name().startswith("postgresql"):
        msg = "TEST_DATABASE_URL must use PostgreSQL."
        raise RuntimeError(msg)
    if not (url.database or "").endswith("_test"):
        msg = "TEST_DATABASE_URL database name must end with '_test'."
        raise RuntimeError(msg)


_ensure_safe_test_database_url(TEST_DATABASE_URL)

os.environ["APP_NAME"] = "Fullstack Context Orchestrator API"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BACKEND_CORS_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
os.environ["AUTH_SECRET_KEY"] = "test-auth-secret"

security = importlib.import_module("app.core.security")
User = importlib.import_module("app.models.user").User
Base = importlib.import_module("app.db.base_class").Base
app = importlib.import_module("app.main").app
db_session_module = importlib.import_module("app.db.session")

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)
db_session_module.engine = engine
db_session_module.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    username = "testuser"
    user = User(
        email="test@example.com",
        username=username,
        password_hash=security.hash_password("StrongPass1!"),
        role="user",
        is_active=True,
        is_email_verified=True,
        avatar_seed=security.make_avatar_seed(username),
        avatar_bg_color=security.make_avatar_color(username),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session: Session, test_user: User) -> Generator[TestClient, None, None]:
    from app.services.generation_queue_service import GenerationQueueService

    GenerationQueueService(db_session).heartbeat_worker("test-worker")

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user.username, "password": "StrongPass1!"},
        )
        assert response.status_code == 200
        yield test_client
