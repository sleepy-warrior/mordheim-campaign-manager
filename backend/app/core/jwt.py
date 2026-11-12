import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


_SUPPORTED_ALGORITHMS = {"HS256", "HS384", "HS512"}


def _jwt_settings() -> tuple[str, str, int]:
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY environment variable is required")

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    if algorithm not in _SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported JWT algorithm: {algorithm}")

    try:
        expires_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    except ValueError as error:
        raise ValueError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be an integer") from error

    if expires_minutes <= 0:
        raise ValueError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

    return secret_key, algorithm, expires_minutes


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    secret_key, algorithm, expires_minutes = _jwt_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=expires_minutes))
    payload: dict[str, Any] = {"sub": subject, "iat": now, "exp": expire}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    secret_key, algorithm, _ = _jwt_settings()
    return jwt.decode(token, secret_key, algorithms=[algorithm])
