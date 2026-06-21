"""Tests for permissions: role/block/action matrix + require_action guard.

Phase 3.1 — locked spec from `docs/03-roles-permissions.md`.
"""
from __future__ import annotations

from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import User
from app.permissions import (
    ALL_BLOCKS,
    can,
    permissions_map,
    require_action,
)
from app.security import hash_password, make_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """Fresh in-memory DB with a clean User table (no seed)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_pragma_on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _make_user(
    db,
    *,
    email: str,
    account_type: str,
    department: Optional[str] = None,
    is_curator: int = 0,
    global_role: Optional[str] = None,
    must_change_password: int = 0,
) -> User:
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name=email,
        account_type=account_type,
        department=department,
        is_curator=is_curator,
        global_role=global_role,
        is_active=1,
        must_change_password=must_change_password,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def admin(db):
    return _make_user(
        db,
        email="admin_t@crm.local",
        account_type="global",
        global_role="Админ",
    )


@pytest.fixture()
def ruk(db):
    return _make_user(
        db,
        email="ruk_t@crm.local",
        account_type="global",
        global_role="Руководитель",
    )


@pytest.fixture()
def zakupki_emp(db):
    return _make_user(
        db,
        email="zak_emp_t@crm.local",
        account_type="department",
        department="Закупки",
        is_curator=0,
    )


@pytest.fixture()
def kompl_emp(db):
    return _make_user(
        db,
        email="kmp_emp_t@crm.local",
        account_type="department",
        department="Комплектация",
        is_curator=0,
    )


@pytest.fixture()
def soprov_emp(db):
    return _make_user(
        db,
        email="spr_emp_t@crm.local",
        account_type="department",
        department="Сопровождение",
        is_curator=0,
    )


@pytest.fixture()
def soprov_curator(db):
    return _make_user(
        db,
        email="spr_cur_t@crm.local",
        account_type="department",
        department="Сопровождение",
        is_curator=1,
    )


# ---------------------------------------------------------------------------
# can() — locked matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("user,block,action,expected", [
    ("zakupki_emp",    "zakupka",        "edit", True),
    ("zakupki_emp",    "komplektaciya",  "edit", False),
    ("zakupki_emp",    "komplektaciya",  "view", True),
    ("soprov_curator", "oplaty",         "edit", True),     # куратор Сопровождения владеет и Оплатами
    ("soprov_curator", "zakupka",        "edit", False),
    ("ruk",            "zakupka",        "edit", False),
    ("ruk",            "reports",        "view", True),
    ("admin",          "admin",          "edit", True),
    ("kompl_emp",      "reports",        "view", False),   # сотрудники отделов не видят отчёты
    ("soprov_emp",     "oplaty",         "edit", False),   # сотрудник Сопровождения НЕ имеет oplaty
    ("soprov_emp",     "soprovozhdenie", "edit", True),
])
def test_can(admin, ruk, zakupki_emp, kompl_emp, soprov_emp, soprov_curator,
             user, block, action, expected):
    fixtures = {
        "admin": admin,
        "ruk": ruk,
        "zakupki_emp": zakupki_emp,
        "kompl_emp": kompl_emp,
        "soprov_emp": soprov_emp,
        "soprov_curator": soprov_curator,
    }
    assert can(fixtures[user], block, action) is expected


# ---------------------------------------------------------------------------
# can() — invalid inputs
# ---------------------------------------------------------------------------

def test_can_none_user_returns_false(admin):
    assert can(None, "zakupka", "edit") is False
    assert can(None, "admin", "view") is False


def test_can_invalid_block_returns_false(admin):
    assert can(admin, "invalid_block", "view") is False


def test_can_invalid_action_returns_false(admin):
    assert can(admin, "zakupka", "delete") is False


# ---------------------------------------------------------------------------
# permissions_map()
# ---------------------------------------------------------------------------

def test_permissions_map_admin_has_all_six_blocks_with_full_access(admin):
    m = permissions_map(admin)
    assert set(m.keys()) == set(ALL_BLOCKS)
    # Admin: view=True everywhere. edit=True on every block EXCEPT reports
    # (reports is read-only for everyone — see Rule 5).
    for block in ALL_BLOCKS:
        assert m[block]["view"] is True, block
        if block == "reports":
            assert m[block]["edit"] is False, block
        else:
            assert m[block]["edit"] is True, block


def test_permissions_map_department_employee_lacks_admin_and_reports(kompl_emp):
    m = permissions_map(kompl_emp)
    assert set(m.keys()) == set(ALL_BLOCKS)
    # Сотрудник Комплектации
    assert m["komplektaciya"]["view"] is True
    assert m["komplektaciya"]["edit"] is True
    assert m["zakupka"]["view"] is True
    assert m["zakupka"]["edit"] is False
    assert m["soprovozhdenie"]["view"] is True
    assert m["soprovozhdenie"]["edit"] is False
    assert m["oplaty"]["view"] is True
    assert m["oplaty"]["edit"] is False
    assert m["reports"]["view"] is False
    assert m["reports"]["edit"] is False
    assert m["admin"]["view"] is False
    assert m["admin"]["edit"] is False


def test_permissions_map_curator_sees_reports(soprov_curator):
    m = permissions_map(soprov_curator)
    assert m["reports"]["view"] is True
    assert m["oplaty"]["view"] is True
    assert m["oplaty"]["edit"] is True


def test_permissions_map_ruk_readonly(ruk):
    m = permissions_map(ruk)
    # View everywhere except admin
    for block in ("komplektaciya", "zakupka", "soprovozhdenie", "oplaty", "reports"):
        assert m[block]["view"] is True, block
    assert m["admin"]["view"] is False
    # All edits False (reports is also read-only)
    for block in ALL_BLOCKS:
        assert m[block]["edit"] is False, block


# ---------------------------------------------------------------------------
# require_action() — FastAPI guard
# ---------------------------------------------------------------------------

def _build_cookie_for(user: User) -> str:
    """Build a session token for the user — used to exercise the real cookie
    path through get_current_user."""
    return make_session(user.id, remember=False)


def test_require_action_admin_admin_edit_returns_user(client_factory, admin):
    """require_action('admin','edit') for an admin returns the user."""
    from fastapi.testclient import TestClient
    from app.db import get_db
    from app.main import app

    # Use the same approach as the other test files: build a fresh TestClient
    # wired to the in-memory db from this fixture.
    client, db = client_factory
    # Login as admin via the real /auth/login flow so we get a valid cookie
    from app.security import hash_password as _hash
    # Reset admin password to known so we can log in
    admin.password_hash = _hash("adminpass123")
    admin.must_change_password = 0
    db.commit()
    r = client.post("/auth/login", json={"email": admin.email, "password": "adminpass123"})
    assert r.status_code == 200, r.text

    # Build a tiny app with a single protected endpoint
    from fastapi import FastAPI, Depends
    from app.permissions import require_action as _ra

    test_app = FastAPI()

    @test_app.get("/probe")
    def _probe(user=Depends(_ra("admin", "edit"))):
        return {"id": user.id, "email": user.email}

    # Mount under the same TestClient by adding a route in-place:
    # simplest: use dependency_overrides on test_app with the same db
    def _override():
        try:
            yield db
        finally:
            pass

    test_app.dependency_overrides[get_db] = _override

    probe_client = TestClient(test_app)
    probe_client.cookies.set("crm_session", r.cookies.get("crm_session"))
    rp = probe_client.get("/probe")
    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert body["email"] == admin.email


def test_require_action_non_admin_returns_403(client_factory, soprov_curator):
    """require_action('admin','edit') for a non-admin raises 403 'forbidden'."""
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    from app.db import get_db
    from app.permissions import require_action as _ra

    client, db = client_factory
    # Login as curator (must_change_password=0 so the guard passes that check)
    from app.security import hash_password as _hash
    soprov_curator.password_hash = _hash("curpass123")
    soprov_curator.must_change_password = 0
    db.commit()
    r = client.post("/auth/login", json={"email": soprov_curator.email, "password": "curpass123"})
    assert r.status_code == 200, r.text

    test_app = FastAPI()

    @test_app.get("/probe")
    def _probe(user=Depends(_ra("admin", "edit"))):
        return {"id": user.id}

    def _override():
        try:
            yield db
        finally:
            pass

    test_app.dependency_overrides[get_db] = _override

    probe_client = TestClient(test_app)
    probe_client.cookies.set("crm_session", r.cookies.get("crm_session"))
    rp = probe_client.get("/probe")
    assert rp.status_code == 403, rp.text
    assert rp.json()["detail"] == "forbidden"


def test_require_action_blocks_when_must_change_password(client_factory, admin):
    """must_change_password=1 must surface as 403 'must change password',
    NOT as 'forbidden' (the password-changed guard fires first)."""
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    from app.db import get_db
    from app.permissions import require_action as _ra

    client, db = client_factory
    admin.must_change_password = 1
    db.commit()
    r = client.post("/auth/login", json={"email": admin.email, "password": "userpass123"})
    assert r.status_code == 200

    test_app = FastAPI()

    @test_app.get("/probe")
    def _probe(user=Depends(_ra("admin", "edit"))):
        return {"id": user.id}

    def _override():
        try:
            yield db
        finally:
            pass

    test_app.dependency_overrides[get_db] = _override

    probe_client = TestClient(test_app)
    probe_client.cookies.set("crm_session", r.cookies.get("crm_session"))
    rp = probe_client.get("/probe")
    assert rp.status_code == 403
    assert rp.json()["detail"] == "must change password"


# ---------------------------------------------------------------------------
# client_factory — built from the `db` fixture so cookie-based tests work
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_factory(db):
    """Yields (TestClient, db_session) wired to the in-memory DB."""
    from fastapi.testclient import TestClient
    from app.db import get_db
    from app.main import app

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.clear()
