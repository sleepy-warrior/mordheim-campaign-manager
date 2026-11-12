from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher


_password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""

    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""

    return _password_hash.verify(password, hashed_password)
