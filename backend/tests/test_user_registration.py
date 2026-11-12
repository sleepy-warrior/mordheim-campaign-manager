import os
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/test",
)

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.main import app


class FakeDatabaseError(Exception):
    def __init__(self, constraint_name: str) -> None:
        self.diag = type("Diagnostic", (), {"constraint_name": constraint_name})()


class FakeSession:
    def __init__(
        self,
        scalar_results: Iterator[Any],
        commit_error: Exception | None = None,
    ) -> None:
        self._scalar_results = scalar_results
        self._commit_error = commit_error
        self.added_user = None
        self.committed = False
        self.rollback_called = False

    def scalar(self, statement: Any) -> Any:
        return next(self._scalar_results)

    def add(self, user: Any) -> None:
        self.added_user = user

    def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error
        self.committed = True

    def rollback(self) -> None:
        self.rollback_called = True
        self.committed = False

    def refresh(self, user: Any) -> None:
        user.id = uuid.uuid4()
        timestamp = datetime.now(timezone.utc)
        user.created_at = timestamp
        user.updated_at = timestamp


def client_for_session(
    session: FakeSession,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    def override_get_db() -> Iterator[FakeSession]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_registers_user_and_excludes_password_from_response() -> None:
    session = FakeSession(iter((None, None)))
    client = client_for_session(session)

    try:
        response = client.post(
            "/api/v1/users/register",
            json={
                "email": "player@example.com",
                "username": "warband_leader",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["email"] == "player@example.com"
    assert response.json()["username"] == "warband_leader"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
    assert session.added_user.password_hash != "secure-password"
    assert session.committed is True


def test_register_normalizes_email_and_rejects_case_insensitive_duplicate() -> None:
    session = FakeSession(iter((None, None, object(), None)))
    client = client_for_session(session)

    try:
        first_response = client.post(
            "/api/v1/users/register",
            json={
                "email": "Player@Example.com",
                "username": "warband_leader",
                "password": "secure-password",
            },
        )
        first_user = session.added_user
        second_response = client.post(
            "/api/v1/users/register",
            json={
                "email": "player@example.com",
                "username": "another_warband",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 201
    assert first_user.email == "player@example.com"
    assert second_response.status_code == 409


def test_register_rejects_duplicate_email_from_precheck() -> None:
    session = FakeSession(iter((object(), None)))
    client = client_for_session(session)

    try:
        response = client.post(
            "/api/v1/users/register",
            json={
                "email": "player@example.com",
                "username": "another_warband",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_register_rejects_duplicate_username_from_precheck() -> None:
    session = FakeSession(iter((None, object())))
    client = client_for_session(session)

    try:
        response = client.post(
            "/api/v1/users/register",
            json={
                "email": "another@example.com",
                "username": "warband_leader",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_register_handles_email_integrity_error_and_rolls_back() -> None:
    error = IntegrityError("insert", {}, FakeDatabaseError("uq_users_email"))
    session = FakeSession(iter((None, None)), commit_error=error)
    client = client_for_session(session)

    try:
        response = client.post(
            "/api/v1/users/register",
            json={
                "email": "player@example.com",
                "username": "warband_leader",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert session.rollback_called is True


def test_register_handles_username_integrity_error_and_rolls_back() -> None:
    error = IntegrityError("insert", {}, FakeDatabaseError("uq_users_username"))
    session = FakeSession(iter((None, None)), commit_error=error)
    client = client_for_session(session)

    try:
        response = client.post(
            "/api/v1/users/register",
            json={
                "email": "player@example.com",
                "username": "warband_leader",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert session.rollback_called is True


def test_register_does_not_mask_other_integrity_errors() -> None:
    error = IntegrityError("insert", {}, FakeDatabaseError("other_constraint"))
    session = FakeSession(iter((None, None)), commit_error=error)
    client = client_for_session(session, raise_server_exceptions=False)

    try:
        response = client.post(
            "/api/v1/users/register",
            json={
                "email": "player@example.com",
                "username": "warband_leader",
                "password": "secure-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert session.rollback_called is True
