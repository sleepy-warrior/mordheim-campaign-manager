from sqlalchemy import select
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.jwt import create_access_token
from app.core.security import verify_password
from app.models import User

from .schemas import LoginRequest


class InvalidCredentialsError(Exception):
    pass


def login_user(db: Session, login_data: LoginRequest) -> tuple[str, str, datetime]:
    normalized_email = str(login_data.email).strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))

    if user is None or not verify_password(login_data.password, user.password_hash):
        raise InvalidCredentialsError

    from .session_service import create_refresh_session

    access_token = create_access_token(str(user.id))
    refresh_token, expires_at = create_refresh_session(db, user.id)
    return access_token, refresh_token, expires_at
