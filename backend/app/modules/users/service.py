from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User

from .schemas import UserCreate


_UNIQUE_CONSTRAINT_FIELDS = {
    "uq_users_email": "email",
    "uq_users_username": "username",
}


class UserAlreadyExistsError(Exception):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"User with this {field} already exists")


def _get_constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def register_user(db: Session, user_data: UserCreate) -> User:
    normalized_email = str(user_data.email).strip().lower()

    if db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
        raise UserAlreadyExistsError("email")

    if db.scalar(select(User.id).where(User.username == user_data.username)) is not None:
        raise UserAlreadyExistsError("username")

    user = User(
        email=normalized_email,
        username=user_data.username,
        password_hash=hash_password(user_data.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        field = _UNIQUE_CONSTRAINT_FIELDS.get(_get_constraint_name(error))
        if field is None:
            raise
        raise UserAlreadyExistsError(field) from error
    except Exception:
        db.rollback()
        raise

    return user


def search_users(db: Session, username: str, exclude_user_id=None) -> list[User]:
    query = select(User).where(User.username.ilike(f"%{username}%")).order_by(User.username).limit(10)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    return list(db.scalars(query).all())
