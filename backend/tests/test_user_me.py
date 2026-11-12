import os
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/test",
)
os.environ["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY") or "test-only-jwt-secret"
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")

from fastapi.testclient import TestClient

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models import User


class FakeSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def scalar(self, statement: Any) -> User | None:
        return self.user


def make_user() -> User:
    timestamp = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="player@example.com",
        username="warband_leader",
        password_hash=hash_password("secure-password"),
        created_at=timestamp,
        updated_at=timestamp,
    )


def client_for_session(session: FakeSession) -> TestClient:
    def override_get_db() -> Iterator[FakeSession]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_get_current_user_returns_user_without_password_fields() -> None:
    user = make_user()
    client = client_for_session(FakeSession(user))

    try:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert response.json()["username"] == user.username
    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_get_current_user_rejects_missing_token() -> None:
    client = client_for_session(FakeSession(make_user()))

    try:
        response = client.get("/api/v1/users/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_get_current_user_rejects_invalid_token() -> None:
    client = client_for_session(FakeSession(make_user()))

    try:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
