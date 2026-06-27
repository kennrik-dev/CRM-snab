"""Tests for /dashboard router (Phase 8.1).

Pattern mirrors tests/test_payments.py: self-contained seeded fixtures,
client_admin (seeded admin, password changed), and role/flow helpers.
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


# --- fixtures (mirror test_payments.py) -----------------------------------------

@pytest.fixture()
def db_seeded():
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
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    client_seeded.post("/auth/change-password", json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD})
    client_seeded.post("/auth/logout")
    r = client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD})
    assert r.status_code == 200
    return client_seeded


# --- helpers -------------------------------------------------------------------

def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_zakupka(client, code, title, positions):
    """parent + positions → take-to-work. Returns procedure_id (block=zakupka)."""
    body = _create_request(client, code, title, positions)
    parent_id = body["id"]
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    return r.json()["procedure_id"]


def _to_support(client, code, title, positions):
    """parent + positions → take-to-work → price → 'На сделку' → to-support.
    Returns procedure_id (block=soprovozhdenie)."""
    proc_id = _to_zakupka(client, code, title, positions)
    proc_positions = client.get(f"/procedures/{proc_id}").json()["positions"]
    for src, proc_pos in zip(positions, proc_positions):
        if src.get("price") is not None:
            client.patch(
                f"/procedures/{proc_id}/positions/{proc_pos['id']}",
                json={"price": src["price"]},
            )
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r2 = client.post(f"/procedures/{proc_id}/to-support")
    assert r2.status_code == 200, r2.text
    return proc_id


def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def _delivery_upd(client, code, title, positions):
    """Procedure → delivery of position 0 → issue УПД. Returns (proc_id, delivery, upd_resp)."""
    proc_id = _to_support(client, code, title, positions)
    pid = _position_ids(client, proc_id)[0]
    d = client.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    upd = client.post(f"/deliveries/{d['id']}/upd", json={"upd": "UPD-" + code}).json()
    return proc_id, d, upd


def _set_proc(db, proc_id, **fields):
    from app.models import Procedure
    db.query(Procedure).filter_by(id=proc_id).update(fields)
    db.commit()


def _set_delivery(db, delivery_id, **fields):
    from app.models import Delivery
    db.query(Delivery).filter_by(id=delivery_id).update(fields)
    db.commit()


def _make_kompl_emp(db, email="kompl_emp@crm.local"):
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name="Комплектовщик Тестовый", account_type="department",
        department="Комплектация", is_curator=0, global_role=None,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login_as(client, email, password="userpass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


# --- 8.1 Task 1: shape + auth ---------------------------------------------------

def test_dashboard_shape_empty(client_admin):
    r = client_admin.get("/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"meters", "flow", "attention", "feed", "tables"}
    assert set(body["tables"].keys()) == {"awaiting", "procurement", "support"}
    for k in ("awaiting", "procurement", "support"):
        assert set(body["tables"][k].keys()) == {"total", "items"}


def test_dashboard_unauth_401(client_seeded):
    # no login at all → 401
    assert client_seeded.get("/dashboard").status_code == 401


def test_dashboard_must_change_403(client_seeded):
    # seed admin BEFORE changing password → must_change_password=1 → 403
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    assert client_seeded.get("/dashboard").status_code == 403


def test_dashboard_ok_for_department_employee(client_seeded, db_seeded):
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/dashboard").status_code == 200
