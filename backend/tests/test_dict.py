"""Tests for /dict router: list (auth+pc) + admin-only mutations.

Phase 3.3 — locked spec.
"""
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
# Fixtures (mirror tests/test_users.py)
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
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200, r.text

    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD},
    )
    assert r_ch.status_code == 200, r_ch.text

    r_lo = client_seeded.post("/auth/logout")
    assert r_lo.status_code == 200

    r_li = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD},
    )
    assert r_li.status_code == 200, r_li.text
    assert r_li.json()["must_change_password"] is False

    return client_seeded


@pytest.fixture()
def client_dept_employee(client_seeded, db_seeded):
    """TestClient logged in as a department (Закупки) non-admin employee."""
    from app.models import User
    u = User(
        email="zakup_emp@crm.local",
        password_hash=hash_password("userpass123"),
        full_name="Закупщик Тестовый",
        account_type="department",
        department="Закупки",
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=0,
    )
    db_seeded.add(u)
    db_seeded.commit()

    r = client_seeded.post(
        "/auth/login",
        json={"email": u.email, "password": "userpass123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is False
    return client_seeded


# ---------------------------------------------------------------------------
# GET /dict/{kind} — list (auth + must_change_password=0)
# ---------------------------------------------------------------------------

def test_get_status_zakup_as_admin_returns_6_seed_values(client_admin):
    r = client_admin.get("/dict/status_zakup")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 6

    # Ordered by sort_order ASC
    sort_orders = [row["sort_order"] for row in body]
    assert sort_orders == sorted(sort_orders)

    values = [row["value"] for row in body]
    assert values == [
        "Приём заявок",
        "Торги",
        "Тех. экспертиза",
        "Дозапросы",
        "Согласование",
        "На сделку",
    ]

    # Shape check
    for row in body:
        assert set(row.keys()) == {"id", "kind", "value", "sort_order"}
        assert row["kind"] == "status_zakup"
        assert isinstance(row["id"], int)
        assert isinstance(row["value"], str)
        assert row["sort_order"] is not None
        assert isinstance(row["sort_order"], int)


def test_get_status_sdelki_returns_3_seed_values(client_admin):
    r = client_admin.get("/dict/status_sdelki")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 3

    values = [row["value"] for row in body]
    assert values == ["Согласование", "Подготовка ДД", "Подписано"]
    for row in body:
        assert row["kind"] == "status_sdelki"


def test_get_dict_unknown_kind_returns_422(client_admin):
    r = client_admin.get("/dict/invalid_kind")
    assert r.status_code == 422


def test_get_dict_unauthenticated_returns_401(client_seeded):
    r = client_seeded.get("/dict/status_zakup")
    assert r.status_code == 401


def test_get_dict_with_must_change_password_returns_403(client_seeded):
    """Admin who has not yet changed password must be 403 on GET /dict."""
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is True

    r2 = client_seeded.get("/dict/status_zakup")
    assert r2.status_code == 403


# ---------------------------------------------------------------------------
# POST /dict/{kind} — admin-only create
# ---------------------------------------------------------------------------

def test_post_dict_as_non_admin_returns_403(client_dept_employee):
    r = client_dept_employee.post(
        "/dict/status_zakup",
        json={"value": "Новый статус", "sort_order": 99},
    )
    assert r.status_code == 403


def test_post_dict_as_admin_creates_and_returns_new_row(client_admin, db_seeded):
    r = client_admin.post(
        "/dict/status_zakup",
        json={"value": "Новый статус", "sort_order": 99},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["value"] == "Новый статус"
    assert body["kind"] == "status_zakup"
    assert body["sort_order"] == 99
    assert isinstance(body["id"], int)

    # GET must now include the new value
    r2 = client_admin.get("/dict/status_zakup")
    assert r2.status_code == 200
    values = [row["value"] for row in r2.json()]
    assert "Новый статус" in values
    assert len(r2.json()) == 7


def test_post_dict_duplicate_value_returns_409(client_admin):
    # Seed already has "Приём заявок" for status_zakup
    r = client_admin.post(
        "/dict/status_zakup",
        json={"value": "Приём заявок", "sort_order": 99},
    )
    assert r.status_code == 409


def test_post_dict_unknown_kind_returns_422(client_admin):
    r = client_admin.post(
        "/dict/bogus_kind",
        json={"value": "Anything", "sort_order": 1},
    )
    assert r.status_code == 422


def test_post_dict_without_sort_order_creates_with_null(client_admin, db_seeded):
    """sort_order is optional → defaults to None in the row."""
    r = client_admin.post(
        "/dict/status_sdelki",
        json={"value": "Завершено"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["value"] == "Завершено"
    assert body["sort_order"] is None


# ---------------------------------------------------------------------------
# DELETE /dict/{kind}/{dict_id} — admin-only delete
# ---------------------------------------------------------------------------

def test_delete_dict_as_admin_removes_row(client_admin, db_seeded):
    # Find an existing dict id
    r = client_admin.get("/dict/status_zakup")
    assert r.status_code == 200
    target_id = r.json()[0]["id"]
    target_value = r.json()[0]["value"]

    r_del = client_admin.delete(f"/dict/status_zakup/{target_id}")
    assert r_del.status_code == 200, r_del.text
    assert r_del.json() == {"ok": True}

    # Value must be gone from GET
    r2 = client_admin.get("/dict/status_zakup")
    assert r2.status_code == 200
    values = [row["value"] for row in r2.json()]
    assert target_value not in values
    assert len(r2.json()) == 5


def test_delete_dict_not_found_returns_404(client_admin):
    r = client_admin.delete("/dict/status_zakup/9999")
    assert r.status_code == 404


def test_delete_dict_as_non_admin_returns_403(client_dept_employee):
    r = client_dept_employee.delete("/dict/status_zakup/1")
    assert r.status_code == 403


def test_delete_dict_unknown_kind_returns_422(client_admin):
    r = client_admin.delete("/dict/bogus_kind/1")
    assert r.status_code == 422
