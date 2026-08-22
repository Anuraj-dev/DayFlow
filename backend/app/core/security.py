from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings
from app.domain.roles import Role

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain)
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    user_id: UUID,
    organization_id: UUID,
    role: Role,
    email: str,
) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role.value,
        "email": email,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
