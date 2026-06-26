"""Tests for /payments router (Phase 7.1).

Pattern mirrors tests/test_support.py: self-contained seeded fixtures,
client_admin (seeded admin, password changed), and role helpers.
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


# --- fixtures (mirror test_support.py) -----------------------------------------

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


def _to_support(client, code, title, positions):
    """parent + positions → take-to-work → price → 'На сделку' → to-support.
    Returns procedure_id (block=soprovozhdenie)."""
    body = _create_request(client, code, title, positions)
    parent_id = body["id"]
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    proc_id = r.json()["procedure_id"]
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


def _make_soprov_emp(db, email="soprov_emp@crm.local"):
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


# --- 7.1 Task 1: GET /payments registry ----------------------------------------

def test_payments_list_empty(client_admin):
    r = client_admin.get("/payments")
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [], "total": 0}


def test_payments_list_shows_delivery_upd_with_joined_fields(client_admin):
    proc_id, d, upd = _delivery_upd(
        client_admin, "PAY-L1", "list one",
        [{"name": "x", "qty": 2.0, "price": 10000}],
    )
    r = client_admin.get("/payments")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["upd"] == "UPD-PAY-L1"
    assert item["origin"] == "delivery"
    assert item["request_display"] == "PAY-L1"      # parent_request.code
    assert item["delivery_n"] == 1
    assert item["pay_status"] == "await"
    assert item["amount"] == 20000                  # 2.0 * 100.00 ₽
    assert item["is_overdue"] is False              # no srok


def test_payments_list_upd_overdue_flag(client_admin, db_seeded):
    from app.models import UpdPayment
    proc_id, d, _upd = _delivery_upd(
        client_admin, "PAY-OVD", "overdue",
        [{"name": "x", "qty": 1.0, "price": 5000}],
    )
    # srok в прошлом (PATCH появляется в Задаче 4 — пока напрямую через БД)
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": "2026-06-01"})
    db_seeded.commit()
    item = client_admin.get("/payments").json()["items"][0]
    assert item["is_overdue"] is True


def test_payments_list_excludes_cancelled_procedure(client_admin):
    proc_id, d, _upd = _delivery_upd(
        client_admin, "PAY-CXL", "cancel",
        [{"name": "x", "qty": 1.0, "price": 1000}],
    )
    # процедура в отмене → её УПД исчезает из реестра
    client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Отменена"})
    body = client_admin.get("/payments").json()
    assert body["total"] == 0


# --- 7.1 Task 2: POST /payments (manual УПД) -----------------------------------

def test_create_manual_upd_happy(client_admin, db_seeded):
    from app.models import UpdPayment
    r = client_admin.post("/payments", json={
        "upd": "UPD-MAN-1", "request_label": "Т-99 №3",
        "supplier": "ООО Ромашка", "srok": "2026-12-31",
        "amount": 1500000, "zrds": "ЗРДС-5",
        "positions": [{"n": 1, "name": "болт", "unit": "шт", "qty": 10.0, "price": 150000}],
    })
    assert r.status_code == 201, r.text
    got = r.json()
    assert got["origin"] == "manual"
    assert got["pay_status"] == "await"
    assert got["amount"] == 1500000
    assert got["delivery_id"] is None
    assert got["delivery"] is None
    assert len(got["positions"]) == 1
    assert got["positions"][0]["name"] == "болт"
    # persisted
    db_seeded.expire_all()
    row = db_seeded.query(UpdPayment).filter_by(upd="UPD-MAN-1").one()
    assert row.origin == "manual"
    assert row.contract is None              # у manual нет договора при создании


def test_create_manual_upd_amount_from_positions(client_admin):
    r = client_admin.post("/payments", json={
        "upd": "UPD-MAN-2", "supplier": "С",
        "positions": [{"qty": 2.0, "price": 5000}, {"qty": 1.0, "price": 10000}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["amount"] == 20000       # 2*5000 + 1*10000


def test_create_manual_upd_empty_upd_422(client_admin):
    r = client_admin.post("/payments", json={"upd": ""})
    assert r.status_code == 422


def test_create_manual_upd_rbac_ok_for_soprov_emp(client_seeded, db_seeded, client_admin):
    _ = client_admin  # seed/seed admin not strictly needed but keeps fixtures warm
    u = _make_soprov_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.post("/payments", json={"upd": "UPD-EMP", "supplier": "S"})
    assert r.status_code == 201, r.text


def test_create_manual_upd_rbac_403_for_kompl_emp(client_seeded, db_seeded, client_admin):
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.post("/payments", json={"upd": "UPD-KOMPL", "supplier": "S"})
    assert r.status_code == 403


def test_create_manual_upd_writes_audit(client_admin, db_seeded):
    from app.models import AuditLog, UpdPayment
    client_admin.post("/payments", json={"upd": "UPD-AUD", "supplier": "S"})
    db_seeded.expire_all()
    payment = db_seeded.query(UpdPayment).filter_by(upd="UPD-AUD").one()
    rows = db_seeded.query(AuditLog).filter_by(
        entity_kind="upd_payment", entity_id=payment.id, action="payment_create"
    ).all()
    assert len(rows) == 1


def test_manual_upd_appears_in_list(client_admin):
    client_admin.post("/payments", json={
        "upd": "UPD-MAN-L", "request_label": "Т-70 №1", "supplier": "Поставщик",
    })
    body = client_admin.get("/payments").json()
    item = next(i for i in body["items"] if i["upd"] == "UPD-MAN-L")
    assert item["origin"] == "manual"
    assert item["request_display"] == "Т-70 №1"
    assert item["delivery_n"] is None
