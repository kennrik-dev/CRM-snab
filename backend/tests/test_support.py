"""Tests for /support + /deliveries routers (Phase 6.2).

Pattern mirrors tests/test_procurement.py. A procedure reaches the support
block via: take-to-work → PATCH status_zakup='На сделку' → POST /to-support.
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


# --- fixtures (mirror test_procurement.py) --------------------------------------

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


# --- helpers --------------------------------------------------------------------

def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_support(client, code, title, positions):
    """Create parent + positions, take to work, advance to 'На сделку',
    hand off to support → returns procedure_id (block=soprovozhdenie)."""
    body = _create_request(client, code, title, positions)
    parent_id = body["id"]
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    proc_id = r.json()["procedure_id"]
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r2 = client.post(f"/procedures/{proc_id}/to-support")
    assert r2.status_code == 200, r2.text
    return proc_id


def _make_soprov_emp(db, email="soprov_emp@crm.local"):
    """Сопровождение employee — has soprovozhdenie edit (NOT oplaty)."""
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name="Сопровождение Тестовое", account_type="department",
        department="Сопровождение", is_curator=0, global_role=None,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


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


# --- 6.2a: GET /procedures/{id} returns Б2 fields + deliveries -------------------

def test_detail_support_block_has_b2_fields(client_admin):
    proc_id = _to_support(client_admin, "SUP-DET", "sopr detail",
                          [{"name": "x", "qty": 10.0}])
    r = client_admin.get(f"/procedures/{proc_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["block"] == "soprovozhdenie"
    for k in ("contract", "fio_dogovornik", "contract_sum", "status_sdelki",
              "status_postavki", "srok_dd", "plan_date", "fakt_date", "deliveries"):
        assert k in body
    assert body["status_postavki"] == "Новая"   # set by to-support
    assert body["deliveries"] == []              # no deliveries yet


# --- 6.2a: PATCH Б2-fields persist (support block); status_sdelki validated ------

def test_patch_b2_fields_persist(client_admin):
    proc_id = _to_support(client_admin, "SUP-PAT", "patch b2",
                          [{"name": "x", "qty": 10.0, "price": 10000}])
    r = client_admin.patch(f"/procedures/{proc_id}", json={
        "contract": "ДК-77", "fio_dogovornik": "Петров П.П.",
        "contract_sum": 1500000, "status_sdelki": "Подписано",
        "status_postavki": "В поставке", "srok_dd": "2026-07-01",
        "plan_date": "2026-06-25", "fakt_date": None,
    })
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["contract"] == "ДК-77"
    assert got["fio_dogovornik"] == "Петров П.П."
    assert got["contract_sum"] == 1500000
    assert got["status_sdelki"] == "Подписано"
    assert got["status_postavki"] == "В поставке"
    assert got["srok_dd"] == "2026-07-01"


def test_patch_status_sdelki_invalid_422(client_admin):
    proc_id = _to_support(client_admin, "SUP-SDELKA-BAD", "bad",
                          [{"name": "x", "qty": 1.0}])
    r = client_admin.patch(f"/procedures/{proc_id}", json={"status_sdelki": "Нет такого"})
    assert r.status_code == 422


def test_patch_status_postavki_invalid_422(client_admin):
    proc_id = _to_support(client_admin, "SUP-POST-BAD", "bad",
                          [{"name": "x", "qty": 1.0}])
    r = client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Лёгкое"})
    assert r.status_code == 422


# --- 6.2a: zakupka PATCH still works (no regression) + block-whitelist -----------

def test_patch_zakupka_fields_still_work(client_admin):
    # procedure still in zakupka (not to-support) → zakupka patch path
    body = _create_request(client_admin, "SUP-ZK", "zk", [{"name": "x", "qty": 1.0}])
    r = client_admin.post(f"/requests/{body['id']}/take-to-work")
    proc_id = r.json()["procedure_id"]
    r2 = client_admin.patch(f"/procedures/{proc_id}", json={"proc": "ZK-1", "status_zakup": "Торги"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["proc"] == "ZK-1"
    assert r2.json()["status_zakup"] == "Торги"


# --- 6.2a: RBAC — kompl emp cannot PATCH support procedure -----------------------

def test_rbac_patch_support_403_for_kompl(client_seeded, db_seeded, client_admin):
    proc_id = _to_support(client_admin, "SUP-RBAC", "rbac",
                          [{"name": "x", "qty": 1.0}])
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.patch(f"/procedures/{proc_id}", json={"contract": "X"})
    assert r.status_code == 403


def test_rbac_patch_support_ok_for_soprov_emp(client_seeded, db_seeded, client_admin):
    proc_id = _to_support(client_admin, "SUP-RBAC2", "rbac ok",
                          [{"name": "x", "qty": 1.0}])
    u = _make_soprov_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.patch(f"/procedures/{proc_id}", json={"contract": "ДК-1"})
    assert r.status_code == 200, r.text
    assert r.json()["contract"] == "ДК-1"
