from app.core.security import hash_password, verify_password


def test_hash_password_returns_argon2id_hash() -> None:
    password = "correct horse battery staple"

    hashed_password = hash_password(password)

    assert isinstance(hashed_password, str)
    assert hashed_password.startswith("$argon2id$")


def test_hash_is_not_equal_to_plaintext_password() -> None:
    password = "correct horse battery staple"

    hashed_password = hash_password(password)

    assert hashed_password != password


def test_verify_password_accepts_correct_password() -> None:
    password = "correct horse battery staple"
    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_verify_password_rejects_incorrect_password() -> None:
    hashed_password = hash_password("correct horse battery staple")

    assert verify_password("wrong password", hashed_password) is False
