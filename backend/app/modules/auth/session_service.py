import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshSession


class InvalidRefreshTokenError(Exception):
    pass


def refresh_token_days() -> int:
    try:
        days = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    except ValueError as error:
        raise RuntimeError("JWT_REFRESH_TOKEN_EXPIRE_DAYS must be an integer") from error
    if days <= 0:
        raise RuntimeError("JWT_REFRESH_TOKEN_EXPIRE_DAYS must be positive")
    return days


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_session(db: Session, user_id: uuid.UUID) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=refresh_token_days())
    db.add(RefreshSession(user_id=user_id, family_id=uuid.uuid4(), token_hash=hash_refresh_token(token), expires_at=expires_at))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return token, expires_at


def rotate_refresh_session(db: Session, token: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(token)).with_for_update())
    if session is None:
        raise InvalidRefreshTokenError
    if session.revoked_at is not None:
        db.execute(update(RefreshSession).where(RefreshSession.family_id == session.family_id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now))
        db.commit()
        raise InvalidRefreshTokenError
    if session.expires_at <= now:
        session.revoked_at = now
        db.commit()
        raise InvalidRefreshTokenError

    session.revoked_at = now
    new_token = secrets.token_urlsafe(48)
    expires_at = now + timedelta(days=refresh_token_days())
    db.add(RefreshSession(user_id=session.user_id, family_id=session.family_id, token_hash=hash_refresh_token(new_token), expires_at=expires_at))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return new_token, expires_at


def revoke_refresh_session(db: Session, token: str) -> None:
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(token)).with_for_update())
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
