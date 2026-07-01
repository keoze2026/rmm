"""Security primitives: password hashing, JWT, and agent token generation.

Uses bcrypt directly (not passlib) to avoid the passlib/bcrypt 4.x
compatibility warnings, and PyJWT instead of the now-unmaintained python-jose.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets

import bcrypt
import jwt

from app.config import settings

# --- Password hashing (admin users) ---------------------------------------

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT (admin auth) ------------------------------------------------------

def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire, "iat": dt.datetime.now(dt.timezone.utc), "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid/expired tokens."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# --- Agent enrollment tokens ----------------------------------------------
# Each machine gets a unique high-entropy token. We store only its SHA-256 hash;
# the plaintext is shown to the admin exactly once and embedded in the agent.

def generate_agent_token() -> tuple[str, str, str]:
    """Return (plaintext_token, token_hash, token_prefix)."""
    raw = secrets.token_urlsafe(settings.AGENT_TOKEN_BYTES)
    return raw, hash_agent_token(raw), raw[:8]


def hash_agent_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
