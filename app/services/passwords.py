from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.errors import ApiError

MIN_LENGTH = 8
_ph = PasswordHasher()
_DUMMY = _ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _ph.verify(password_hash or _DUMMY, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise ApiError(400, "WEAK_PASSWORD", f"Password must be at least {MIN_LENGTH} characters.")
    if len(password) > 256:
        raise ApiError(400, "WEAK_PASSWORD", "Password is too long.")
