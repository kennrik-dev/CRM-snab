"""Tests for auth router: /auth/login, /auth/logout, /auth/me, /auth/change-password."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import (
    SESSION_COOKIE,
    make_session,
    read_session,
    session_cookie_kwargs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_seeded():
    """In-memory DB with seed_initial applied."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _setup(dbapi_conn, _):
        register_sqlite_setup(dbapi_conn, _)

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    from app.seed import seed_initial
    seed_initial(s)
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client_seeded(db_seeded):
    """TestClient with get_db overridden to the seeded in-memory DB."""

    def _override():
        try:
            yield db_seeded
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


ADMIN_EMAIL = "admin@crm.local"
ADMIN_PASSWORD = "change-me-123"
NEW_STRONG_PASSWORD = "Sup3rStrong!Pass"


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------

def test_login_with_correct_credentials_returns_200_and_sets_cookie(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "remember_me": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["must_change_password"] is True
    assert SESSION_COOKIE in r.cookies
    # Cookie must be httponly + samesite=lax (per session_cookie_kwargs default)
    morsel = r.cookies.get(SESSION_COOKIE)
    assert morsel is not None


def test_login_wrong_credentials_returns_401_no_hint(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": "definitely-wrong-pw"},
    )
    assert r.status_code == 401
    body_text = r.text.lower()
    # Generic message: should not mention "password" or "email" as a hint
    assert "password" not in body_text
    assert "email" not in body_text


def test_login_inactive_user_returns_401(client_seeded, db_seeded):
    # Deactivate the admin
    from app.models import User
    admin = db_seeded.query(User).filter_by(email=ADMIN_EMAIL).one()
    admin.is_active = 0
    db_seeded.commit()

    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------

def test_me_returns_user_and_must_change_true(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    r2 = client_seeded.get("/auth/me")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["must_change_password"] is True
    assert body["user"]["email"] == ADMIN_EMAIL
    # permissions map is present (placeholder)
    assert "permissions" in body
    assert isinstance(body["permissions"], dict)


def test_unauthenticated_me_returns_401(client_seeded):
    r = client_seeded.get("/auth/me")
    assert r.status_code == 401


def test_must_change_password_allows_change_password_and_me(client_seeded):
    # Login (admin has must_change_password=1)
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    # /auth/me must be allowed even with must_change_password=1
    r_me = client_seeded.get("/auth/me")
    assert r_me.status_code == 200

    # /auth/change-password must be allowed even with must_change_password=1
    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_PASSWORD, "new": NEW_STRONG_PASSWORD},
    )
    assert r_ch.status_code == 200, r_ch.text


# ---------------------------------------------------------------------------
# /auth/change-password
# ---------------------------------------------------------------------------

def test_change_password_clears_flag_and_updates_hash(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_PASSWORD, "new": NEW_STRONG_PASSWORD},
    )
    assert r_ch.status_code == 200, r_ch.text
    assert r_ch.json()["ok"] is True

    # must_change_password must now be false
    r_me = client_seeded.get("/auth/me")
    assert r_me.status_code == 200
    assert r_me.json()["must_change_password"] is False

    # Logout, then login with new password
    r_lo = client_seeded.post("/auth/logout")
    assert r_lo.status_code == 200

    # Old password should fail
    r_old = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r_old.status_code == 401

    # New password should succeed
    r_new = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": NEW_STRONG_PASSWORD},
    )
    assert r_new.status_code == 200
    assert r_new.json()["must_change_password"] is False


def test_change_password_wrong_current_returns_401(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": "wrong-current-pw", "new": NEW_STRONG_PASSWORD},
    )
    assert r_ch.status_code == 401


def test_change_password_short_new_returns_422(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_PASSWORD, "new": "short"},
    )
    assert r_ch.status_code == 422


# ---------------------------------------------------------------------------
# /auth/logout
# ---------------------------------------------------------------------------

def test_logout_clears_cookie(client_seeded):
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    r_lo = client_seeded.post("/auth/logout")
    assert r_lo.status_code == 200
    assert r_lo.json()["ok"] is True

    # Subsequent /auth/me must 401
    r_me = client_seeded.get("/auth/me")
    assert r_me.status_code == 401


# ---------------------------------------------------------------------------
# Idle-timeout
# ---------------------------------------------------------------------------

def test_session_idle_timeout_expires(client_seeded):
    """An expired last_active cookie must be rejected by /auth/me."""
    # Build a token whose last_active is far in the past (idle expired).
    long_ago = datetime.now(timezone.utc) - timedelta(hours=10)
    expired_token = make_session(user_id=1, remember=False, now=long_ago)

    # Sanity: the security layer itself must reject it.
    assert read_session(expired_token) is None

    # Manually attach the expired cookie and call /auth/me.
    client_seeded.cookies.set(SESSION_COOKIE, expired_token)
    r = client_seeded.get("/auth/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Cookie attributes
# ---------------------------------------------------------------------------

def test_cookie_attrs_match_session_cookie_kwargs(client_seeded):
    """Confirm that the Set-Cookie header carries httponly + samesite=lax."""
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie or "samesite=lax" in set_cookie.lower()
