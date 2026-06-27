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


# --- 8.1 Task 2: meters + flow -------------------------------------------------

POS1 = [{"name": "x", "qty": 2.0, "unit": "шт", "price": 10000}]   # 2 * 100.00 = 20000


def _meters(client):
    return {m["key"]: m for m in client.get("/dashboard").json()["meters"]}


def _flow(client):
    return {s["key"]: s for s in client.get("/dashboard").json()["flow"]}


def test_meter_in_zakupka_count(client_admin):
    _to_zakupka(client_admin, "D-Z1", "z1", POS1)
    _to_zakupka(client_admin, "D-Z2", "z2", POS1)
    m = _meters(client_admin)
    assert m["in_zakupka"]["value"] == 2
    assert m["in_zakupka"]["sub"] == "процедур"
    assert m["in_zakupka"]["amount"] is None
    assert m["in_zakupka"]["seg"]["total"] == 14


def test_meter_in_zakupka_excludes_cancelled(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "D-ZX", "zx", POS1)
    # «Отменена» is a service value (PATCH→422) — set it directly on the row.
    _set_proc(db_seeded, pid, status_zakup="Отменена")
    assert _meters(client_admin)["in_zakupka"]["value"] == 0


def test_meter_in_support_count_and_contract_sum(client_admin, db_seeded):
    pid = _to_support(client_admin, "D-S1", "s1", POS1)
    _set_proc(db_seeded, pid, contract_sum=1500000)   # 15 000.00 ₽
    m = _meters(client_admin)
    assert m["in_support"]["value"] == 1
    assert m["in_support"]["amount"] == 1500000
    assert m["in_support"]["sub"] is None


def test_meter_in_support_excludes_completed(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-SC", "sc", POS1)
    # mark delivered + pay the УПД → completed
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")
    _set_proc(db_seeded, pid, status_postavki="Поставлено", srok_dd="2026-06-30")
    list_id = client_admin.get("/payments").json()["items"][0]["id"]
    client_admin.post(f"/payments/{list_id}/pay")
    # completed → not in operational counters
    assert _meters(client_admin)["in_support"]["value"] == 0


def test_meter_on_time_pct(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-OT", "ot", POS1)
    _set_proc(db_seeded, pid, srok_dd="2026-06-30")            # future deadline
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")  # before srok → on time
    m = _meters(client_admin)
    assert m["on_time_pct"]["value"] == 100
    assert m["on_time_pct"]["unit"] == "%"
    assert m["on_time_pct"]["sub"] == "1 / 1 поставок"


def test_meter_on_time_late_reduces_pct(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-OT2", "ot2", POS1)
    _set_proc(db_seeded, pid, srok_dd="2026-06-01")            # past deadline
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")  # after srok → late
    assert _meters(client_admin)["on_time_pct"]["value"] == 0  # 0 of 1 on time


def test_meter_overdue_count_and_sum(client_admin, db_seeded):
    pid = _to_support(client_admin, "D-OV", "ov", POS1)
    # position price 100.00 × 2 = 20000; srok in past, not delivered → overdue
    _set_proc(db_seeded, pid, srok_dd="2026-06-01", contract_sum=500000)
    m = _meters(client_admin)
    assert m["overdue"]["value"] == 1
    assert m["overdue"]["amount"] == 500000          # contract_sum used


def test_meter_upd_await_and_overdue(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-UA", "ua", POS1)  # await, amount 20000
    # make it overdue: past srok
    from app.models import UpdPayment
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": "2026-06-01"})
    db_seeded.commit()
    m = _meters(client_admin)
    assert m["upd_await"]["value"] == 1
    assert m["upd_await"]["amount"] == 20000
    assert m["upd_overdue"]["value"] == 1
    assert m["upd_overdue"]["amount"] == 20000


def test_meter_upd_excludes_cancelled_procedure(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-UC", "uc", POS1)
    _set_proc(db_seeded, pid, status_postavki="Отменена")
    m = _meters(client_admin)
    assert m["upd_await"]["value"] == 0
    assert m["upd_overdue"]["value"] == 0


def test_flow_four_stages_counts_and_routes(client_admin):
    _create_request(client_admin, "D-AW", "aw", POS1)          # awaiting (no tender)
    _to_zakupka(client_admin, "D-FZ", "fz", POS1)              # in zakupka
    f = _flow(client_admin)
    assert set(f.keys()) == {"awaiting", "procurement", "support", "payments"}
    assert f["awaiting"]["count"] == 1
    assert f["awaiting"]["route"] == "/komplektaciya"
    assert f["procurement"]["count"] == 1
    assert f["procurement"]["route"] == "/zakupka"
    assert f["support"]["count"] == 0
    assert f["support"]["route"] == "/soprovozhdenie"
    assert f["payments"]["count"] == 0
    assert f["payments"]["route"] == "/oplaty"
