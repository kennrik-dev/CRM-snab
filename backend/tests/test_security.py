"""Tests for app/security.py — password validation + session tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import security
from app.security import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    make_session,
    read_session,
    session_cookie_kwargs,
    validate_password,
)


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

def test_validate_password_accepts_8_chars():
    # Exactly 8 chars must be accepted and not raise.
    validate_password("abcdefgh")


def test_validate_password_rejects_7_chars():
    with pytest.raises(ValueError):
        validate_password("abcdefg")


# ---------------------------------------------------------------------------
# Hash/verify still work (Phase 1 regression check)
# ---------------------------------------------------------------------------

def test_hash_and_verify_roundtrip():
    h = security.hash_password("sup3rsecret!")
    assert h != "sup3rsecret!"
    assert security.verify_password("sup3rsecret!", h) is True
    assert security.verify_password("wrong", h) is False


# ---------------------------------------------------------------------------
# Session tokens
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_make_session_returns_string():
    tok = make_session(user_id=42, now=_now())
    assert isinstance(tok, str)
    assert len(tok) > 0


def test_session_roundtrip_within_idle_window():
    t0 = _now()
    tok = make_session(user_id=42, now=t0)
    # 119 min later — still within 120-min idle window
    payload = read_session(tok, now=t0 + timedelta(minutes=119))
    assert payload is not None
    assert payload["user_id"] == 42


def test_session_expires_after_idle():
    t0 = _now()
    tok = make_session(user_id=42, now=t0)
    # 121 min later — beyond 120-min idle window
    payload = read_session(tok, now=t0 + timedelta(minutes=121))
    assert payload is None


def test_session_invalid_signature_returns_None():
    tok = make_session(user_id=42, now=_now())
    tampered = tok[:-1] + ("A" if tok[-1] != "A" else "B")
    assert read_session(tampered, now=_now()) is None


def test_remember_me_extends_ttl():
    t0 = _now()
    tok = make_session(user_id=42, remember=True, now=t0)
    # 5 days later — still valid because remember=True uses long TTL.
    payload = read_session(tok, now=t0 + timedelta(days=5))
    assert payload is not None
    assert payload["user_id"] == 42


# ---------------------------------------------------------------------------
# Cookie kwargs helper
# ---------------------------------------------------------------------------

def test_session_cookie_kwargs_shape():
    kw = session_cookie_kwargs(secure=False)
    assert kw["httponly"] is True
    assert kw["samesite"] == "lax"
    assert kw["path"] == "/"
    assert kw["secure"] is False

    kw2 = session_cookie_kwargs(secure=True)
    assert kw2["secure"] is True
    assert kw2["httponly"] is True
    assert kw2["samesite"] == "lax"
    assert kw2["path"] == "/"


# Sanity: constants exposed
def test_session_constants_exposed():
    assert SESSION_COOKIE == "crm_session"
    assert SESSION_MAX_AGE == 60 * 60 * 24 * 30
