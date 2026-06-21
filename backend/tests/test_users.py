"""Tests for users router: admin-only /users CRUD + reset-password."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"


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


@pytest.fixture()
def client_admin(client_seeded):
    """TestClient logged in as admin with must_change_password=0."""
    # Login as admin (still has must_change_password=1 from seed)
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200, r.text

    # Change password to flip must_change_password flag to 0
    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD},
    )
    assert r_ch.status_code == 200, r_ch.text

    # Re-login with new password so the cookie reflects the new hash
    r_lo = client_seeded.post("/auth/logout")
    assert r_lo.status_code == 200

    r_li = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD},
    )
    assert r_li.status_code == 200, r_li.text
    assert r_li.json()["must_change_password"] is False

    return client_seeded


# ---------------------------------------------------------------------------
# Helper to insert a non-admin user directly via DB
# ---------------------------------------------------------------------------

def _make_department_user(db, email="zakup_emp@crm.local", department="Закупки"):
    from app.models import User
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name="Закупщик Тестовый",
        account_type="department",
        department=department,
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# /users — list
# ---------------------------------------------------------------------------

def test_admin_can_list_users(client_admin):
    r = client_admin.get("/users")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["email"] == ADMIN_EMAIL


def test_list_users_unauthenticated_returns_401(client_seeded):
    r = client_seeded.get("/users")
    assert r.status_code == 401


def test_non_admin_cannot_list_users(client_seeded, db_seeded):
    # Create a non-admin department user
    user = _make_department_user(db_seeded)

    # Login as that user
    r = client_seeded.post(
        "/auth/login",
        json={"email": user.email, "password": "userpass123"},
    )
    assert r.status_code == 200

    # List users — must be 403
    r2 = client_seeded.get("/users")
    assert r2.status_code == 403


# ---------------------------------------------------------------------------
# /users — create
# ---------------------------------------------------------------------------

def test_non_admin_cannot_create_user(client_seeded, db_seeded):
    user = _make_department_user(db_seeded)

    r = client_seeded.post(
        "/auth/login",
        json={"email": user.email, "password": "userpass123"},
    )
    assert r.status_code == 200

    r2 = client_seeded.post(
        "/users",
        json={
            "email": "newby@crm.local",
            "full_name": "Новый Сотрудник",
            "account_type": "department",
            "department": "Закупки",
            "is_curator": False,
            "global_role": None,
            "password": "newuser123",
        },
    )
    assert r2.status_code == 403


def test_admin_can_create_department_user(client_admin, db_seeded):
    r = client_admin.post(
        "/users",
        json={
            "email": "dep_user@crm.local",
            "full_name": "Закупщик Новый",
            "account_type": "department",
            "department": "Закупки",
            "is_curator": False,
            "global_role": None,
            "password": "newuser123",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "id" in body
    assert body["is_active"] == 1
    assert body["must_change_password"] == 1
    assert body["email"] == "dep_user@crm.local"
    assert body["account_type"] == "department"
    assert body["department"] == "Закупки"


def test_admin_can_create_global_user(client_admin):
    r = client_admin.post(
        "/users",
        json={
            "email": "rukovod@crm.local",
            "full_name": "Руководитель Тестовый",
            "account_type": "global",
            "department": None,
            "is_curator": False,
            "global_role": "Руководитель",
            "password": "rukpwd123",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["account_type"] == "global"
    assert body["global_role"] == "Руководитель"
    assert body["department"] is None
    assert body["must_change_password"] == 1


def test_create_user_with_invalid_department_returns_422(client_admin):
    r = client_admin.post(
        "/users",
        json={
            "email": "baddept@crm.local",
            "full_name": "Плохой Отдел",
            "account_type": "department",
            "department": "Foo",
            "is_curator": False,
            "global_role": None,
            "password": "validpwd123",
        },
    )
    assert r.status_code == 422


def test_create_user_with_invalid_global_role_returns_422(client_admin):
    r = client_admin.post(
        "/users",
        json={
            "email": "badrole@crm.local",
            "full_name": "Плохая Роль",
            "account_type": "global",
            "department": None,
            "is_curator": False,
            "global_role": "Супермен",
            "password": "validpwd123",
        },
    )
    assert r.status_code == 422


def test_create_user_duplicate_email_returns_409(client_admin):
    payload = {
        "email": "dup@crm.local",
        "full_name": "Дубль",
        "account_type": "department",
        "department": "Закупки",
        "is_curator": False,
        "global_role": None,
        "password": "validpwd123",
    }
    r1 = client_admin.post("/users", json=payload)
    assert r1.status_code == 200, r1.text

    r2 = client_admin.post("/users", json=payload)
    assert r2.status_code == 409


def test_create_user_short_password_returns_422(client_admin):
    r = client_admin.post(
        "/users",
        json={
            "email": "shortpw@crm.local",
            "full_name": "Короткий Пароль",
            "account_type": "department",
            "department": "Закупки",
            "is_curator": False,
            "global_role": None,
            "password": "short",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /users/{id} — patch
# ---------------------------------------------------------------------------

def test_admin_can_update_user_full_name(client_admin, db_seeded):
    user = _make_department_user(db_seeded)

    r = client_admin.patch(
        f"/users/{user.id}",
        json={"full_name": "Новый"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Новый"
    assert body["email"] == user.email  # unchanged


def test_update_user_not_found_returns_404(client_admin):
    r = client_admin.patch(
        "/users/9999",
        json={"full_name": "Призрак"},
    )
    assert r.status_code == 404


def test_admin_can_deactivate_user(client_admin, db_seeded):
    user = _make_department_user(db_seeded)

    r = client_admin.patch(
        f"/users/{user.id}",
        json={"is_active": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] == 0

    # That user must not be able to log in
    client_admin.post("/auth/logout")
    r_login = client_admin.post(
        "/auth/login",
        json={"email": user.email, "password": "userpass123"},
    )
    assert r_login.status_code == 401


def test_admin_cannot_deactivate_self(client_admin, db_seeded):
    from app.models import User
    admin = db_seeded.query(User).filter_by(email=ADMIN_EMAIL).one()

    r = client_admin.patch(
        f"/users/{admin.id}",
        json={"is_active": False},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /users/{id}/reset-password
# ---------------------------------------------------------------------------

def test_admin_can_reset_password(client_admin, db_seeded):
    from app.models import User
    user = _make_department_user(db_seeded)

    r = client_admin.post(
        f"/users/{user.id}/reset-password",
        json={"new_password": "newpass123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # must_change_password must be 1
    db_seeded.expire_all()
    u = db_seeded.query(User).filter_by(id=user.id).one()
    assert u.must_change_password == 1

    # Old password should fail login
    client_admin.post("/auth/logout")
    r_old = client_admin.post(
        "/auth/login",
        json={"email": user.email, "password": "userpass123"},
    )
    assert r_old.status_code == 401

    # New password should succeed
    r_new = client_admin.post(
        "/auth/login",
        json={"email": user.email, "password": "newpass123"},
    )
    assert r_new.status_code == 200, r_new.text
    assert r_new.json()["must_change_password"] is True


def test_reset_password_short_returns_422(client_admin, db_seeded):
    user = _make_department_user(db_seeded)

    r = client_admin.post(
        f"/users/{user.id}/reset-password",
        json={"new_password": "short"},
    )
    assert r.status_code == 422


def test_reset_password_user_not_found_returns_404(client_admin):
    r = client_admin.post(
        "/users/9999/reset-password",
        json={"new_password": "validpwd123"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# must_change_password blocks admin mutations
# ---------------------------------------------------------------------------

def test_must_change_password_blocks_admin_mutations(client_seeded):
    """Fresh admin who has not yet changed password:
    - POST /users — 403
    - POST /users/{id}/reset-password — 403
    - POST /auth/change-password — 200
    """
    # Login as fresh admin
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is True

    # Create a user via DB to get a target id for reset-password
    from app.models import User
    from app.security import hash_password
    target = User(
        email="victim@crm.local",
        password_hash=hash_password("victimpwd"),
        full_name="Жертва",
        account_type="department",
        department="Закупки",
        is_active=1,
        must_change_password=0,
    )
    # Get the DB session from the TestClient (it's the seeded one)
    # We need direct DB access — use the dependency override path
    # Simpler: create user via API later. For now skip if not available.
    # Actually — we cannot reach db_seeded here directly; use raw API instead.

    # POST /users should be blocked
    r_create = client_seeded.post(
        "/users",
        json={
            "email": "blocked@crm.local",
            "full_name": "Заблокирован",
            "account_type": "department",
            "department": "Закупки",
            "is_curator": False,
            "global_role": None,
            "password": "validpwd123",
        },
    )
    assert r_create.status_code == 403

    # POST /users/{id}/reset-password should also be blocked (404 vs 403 — the
    # auth check fires first because require_password_changed runs before the
    # handler, so 403 is expected)
    r_reset = client_seeded.post(
        "/users/1/reset-password",
        json={"new_password": "newpwd123"},
    )
    assert r_reset.status_code == 403

    # /auth/change-password must still be allowed
    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": "newpwd123"},
    )
    assert r_ch.status_code == 200, r_ch.text
