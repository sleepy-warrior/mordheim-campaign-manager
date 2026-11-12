"""Create deterministic local development users without changing existing rows.

Run explicitly with APP_ENV=development and SEED_DEV_USERS=true.
"""
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


USERS = (
    ("admin", "admin@example.com", "admin"),
    ("test", "test@example.com", "test"),
)


def main() -> int:
    if os.getenv("APP_ENV") not in {"development", "local"} or os.getenv("SEED_DEV_USERS") != "true":
        print("Refusing to seed users: require APP_ENV=development|local and SEED_DEV_USERS=true.", file=sys.stderr)
        return 2

    with SessionLocal.begin() as db:
        for username, email, password in USERS:
            existing = db.scalar(select(User).where(User.username == username))
            if existing is not None:
                email_owner = db.scalar(select(User).where(User.email == email, User.id != existing.id))
                if email_owner is not None:
                    raise RuntimeError(f"Cannot update {username}: email {email} belongs to another user")
                if existing.email != email:
                    existing.email = email
                    print(f"updated email: {username}")
                else:
                    print(f"exists: {username}")
                continue
            db.add(User(email=email, username=username, password_hash=hash_password(password)))
            print(f"created: {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
