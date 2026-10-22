import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()  # Argon2
_JWT_ALGORITHM = "HS256"

# A real hash to compare against when the user doesn't exist, so a "no such user" login takes
# as long as a "wrong password" login (otherwise response timing reveals which emails exist).
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, hashed)


def create_access_token(subject_id: uuid.UUID, token_type: str = "access") -> str:
    """token_type "access" = clinic staff, "patient" = patient app. They never mix."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject_id),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, token_type: str = "access") -> uuid.UUID | None:
    """Returns the subject id if the token is valid, unexpired and of the given type."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[_JWT_ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def generate_token() -> str:
    """A long random string for refresh tokens, reset links and invitations."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
