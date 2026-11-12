import os
from datetime import datetime, timezone
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import RefreshSession

from .schemas import LoginRequest, TokenResponse
from .service import InvalidCredentialsError, login_user
from .session_service import InvalidRefreshTokenError, revoke_refresh_session, rotate_refresh_session


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE = "mordheim_refresh_token"


def _check_csrf(request: Request) -> None:
    expected_origin = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") != expected_origin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def _set_refresh_cookie(response: Response, token: str, expires_at) -> None:
    max_age = max(1, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(REFRESH_COOKIE, token, max_age=max_age, expires=max_age, httponly=True, secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", samesite="lax", path="/api/v1/auth")


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        access_token, refresh_token, expires_at = login_user(db, login_data)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    _set_refresh_cookie(response, refresh_token, expires_at)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    _check_csrf(request)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        refresh_token, expires_at = rotate_refresh_session(db, token)
        from app.core.jwt import create_access_token
        session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hashlib.sha256(refresh_token.encode()).hexdigest()))
        if session is None:
            raise InvalidRefreshTokenError
        access_token = create_access_token(str(session.user_id))
    except (InvalidRefreshTokenError, RuntimeError):
        response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    _set_refresh_cookie(response, refresh_token, expires_at)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    _check_csrf(request)
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        revoke_refresh_session(db, token)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
