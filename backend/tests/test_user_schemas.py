import os
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/test",
)

from app.models import User
from app.modules.users.schemas import UserCreate, UserResponse


def test_user_create_accepts_valid_data() -> None:
    user = UserCreate(
        email="player@example.com",
        username="warband_leader",
        password="secure-password",
    )

    assert user.email == "player@example.com"
    assert user.username == "warband_leader"
    assert user.password == "secure-password"


def test_user_create_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="not-an-email",
            username="warband_leader",
            password="secure-password",
        )


@pytest.mark.parametrize("username", ["ab", "a" * 101])
def test_user_create_rejects_invalid_username_length(username: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="player@example.com",
            username=username,
            password="secure-password",
        )


def test_user_create_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="player@example.com",
            username="warband_leader",
            password="short",
        )


def test_user_response_can_be_created_from_sqlalchemy_model() -> None:
    timestamp = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email="player@example.com",
        username="warband_leader",
        password_hash="hashed-password",
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = UserResponse.model_validate(user)

    assert response.id == user.id
    assert response.email == user.email
    assert response.username == user.username
    assert response.created_at == user.created_at
    assert response.updated_at == user.updated_at


def test_user_response_does_not_expose_password_fields() -> None:
    response_fields = UserResponse.model_fields
    response_data = UserResponse(
        id=uuid.uuid4(),
        email="player@example.com",
        username="warband_leader",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ).model_dump()

    assert "password" not in response_fields
    assert "password_hash" not in response_fields
    assert "password" not in response_data
    assert "password_hash" not in response_data
