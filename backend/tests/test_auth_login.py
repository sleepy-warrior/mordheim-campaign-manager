import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/test",
)
os.environ["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY") or "test-only-jwt-secret"
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.jwt import create_access_token, decode_access_token
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models import RefreshSession, User
from app.modules.auth.session_service import InvalidRefreshTokenError, hash_refresh_token, rotate_refresh_session


class FakeSession:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.added = []
        self.rollback_called = False

    def scalar(self, statement: Any) -> User | None:
        return self.user

    def add(self, value: Any) -> None:
        self.added.append(value)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        self.rollback_called = True


def make_user(password: str = "secure-password") -> User:
    timestamp = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="player@example.com",
        username="warband_leader",
        password_hash=hash_password(password),
        created_at=timestamp,
        updated_at=timestamp,
    )


def client_for_session(session: FakeSession) -> TestClient:
    def override_get_db() -> Iterator[FakeSession]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_login_returns_access_token_for_valid_credentials() -> None:
    user = make_user()
    client = client_for_session(FakeSession(user))

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "PLAYER@EXAMPLE.COM", "password": "secure-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
    assert "mordheim_refresh_token=" in response.headers["set-cookie"]

    payload = decode_access_token(response.json()["access_token"])
    assert payload["sub"] == str(user.id)


def test_login_rejects_invalid_password_with_generic_401() -> None:
    client = client_for_session(FakeSession(make_user()))

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "player@example.com", "password": "wrong-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_unknown_email_with_same_401() -> None:
    client = client_for_session(FakeSession(None))

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "secure-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token("user-id", expires_delta=timedelta(seconds=-1))

    try:
        decode_access_token(token)
    except jwt.ExpiredSignatureError:
        pass
    else:
        raise AssertionError("Expired access token was accepted")


class RefreshFakeSession:
    def __init__(self, session: RefreshSession) -> None:
        self.session = session
        self.added: list[RefreshSession] = []
        self.committed = 0
        self.rollback_called = False

    def scalar(self, statement: Any) -> RefreshSession:
        return self.session

    def add(self, value: RefreshSession) -> None:
        self.added.append(value)

    def execute(self, statement: Any) -> None:
        self.session.revoked_at = datetime.now(timezone.utc)

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rollback_called = True


def test_refresh_rotation_revokes_old_token_and_reuse_revokes_family() -> None:
    session = RefreshSession(user_id=uuid.uuid4(), family_id=uuid.uuid4(), token_hash=hash_refresh_token("old-token"), expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    db = RefreshFakeSession(session)

    new_token, expires_at = rotate_refresh_session(db, "old-token")

    assert new_token != "old-token"
    assert expires_at > datetime.now(timezone.utc)
    assert session.revoked_at is not None
    assert len(db.added) == 1

    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_session(db, "old-token")
    assert db.committed == 2


def test_refresh_endpoint_rejects_cross_origin_requests() -> None:
    client = client_for_session(FakeSession(None))
    try:
        response = client.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"
