"""Authentication primitives: password hashing + session tokens."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.config import settings


# ---------------------------------------------------------------------------
# Cookie / session constants
# ---------------------------------------------------------------------------

SESSION_COOKIE = "crm_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days for "remember me"


# ---------------------------------------------------------------------------
# Password hashing (Phase 1 — preserved)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Password validation (Phase 2.1 — per 04-auth §4)
# ---------------------------------------------------------------------------

def validate_password(plain: str) -> None:
    """Raise ValueError if password is shorter than 8 characters."""
    if len(plain) < 8:
        raise ValueError("Password must be at least 8 characters long")


# ---------------------------------------------------------------------------
# Session tokens (Phase 2.1 — itsdangerous TimestampSigner)
# ---------------------------------------------------------------------------

def _signer() -> TimestampSigner:
    return TimestampSigner(settings.SESSION_SECRET)


def _utcnow(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def make_session(user_id: int, remember: bool = False, now: datetime | None = None) -> str:
    """Sign a session payload and return the token string."""
    ts = _utcnow(now)
    payload = {
        "user_id": int(user_id),
        "last_active": int(ts.timestamp()),
        "remember": bool(remember),
    }
    max_age = SESSION_MAX_AGE if remember else settings.IDLE_TIMEOUT_MIN * 60
    return _signer().sign(json.dumps(payload, separators=(",", ":"))).decode("utf-8")


def read_session(token: str, now: datetime | None = None) -> dict[str, Any] | None:
    """Verify a session token and return its payload, or None on failure."""
    ts = _utcnow(now)
    idle_max_age = settings.IDLE_TIMEOUT_MIN * 60

    # First, try with the long (remember) max_age. If remember=True this is
    # the only relevant window; if not, we still need this step to recover
    # the payload so we can apply the idle-timeout check below.
    try:
        raw = _signer().unsign(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if "user_id" not in payload or "last_active" not in payload:
        return None

    if payload.get("remember"):
        # Long-lived session — only enforce signature max_age (already done).
        return payload

    # Idle-timeout check: last_active must be within IDLE_TIMEOUT_MIN of now.
    last_active = int(payload["last_active"])
    age_seconds = int(ts.timestamp()) - last_active
    if age_seconds < 0 or age_seconds > idle_max_age:
        return None

    return payload


# ---------------------------------------------------------------------------
# Cookie kwargs helper
# ---------------------------------------------------------------------------

def session_cookie_kwargs(secure: bool = False) -> dict[str, Any]:
    """Standard kwargs for setting the session cookie."""
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
    }


__all__ = [
    "SESSION_COOKIE",
    "SESSION_MAX_AGE",
    "hash_password",
    "verify_password",
    "validate_password",
    "make_session",
    "read_session",
    "session_cookie_kwargs",
]
