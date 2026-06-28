"""Tests for /reports router (Phase 9.1). Mirrors tests/test_dashboard.py."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.calculations import today_moscow
from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"
TODAY = today_moscow()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def last_month_date() -> str:
    # a date firmly in the previous calendar month (robust regardless of today's day)
    first_this = TODAY.replace(day=1)
    return (first_this - timedelta(days=5)).isoformat()


# --- fixtures (mirror test_dashboard.py) ---------------------------------------

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

POS = [{"name": "x", "qty": 2.0, "unit": "шт", "price": 10000}]   # 2 * 100.00 = 20000 kop


def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_zakupka(client, code, title, positions):
    body = _create_request(client, code, title, positions)
    r = client.post(f"/requests/{body['id']}/take-to-work")
    assert r.status_code == 200, r.text
    return r.json()["procedure_id"]


def _to_support(client, code, title, positions):
    proc_id = _to_zakupka(client, code, title, positions)
    for src, pp in zip(positions, client.get(f"/procedures/{proc_id}").json()["positions"]):
        if src.get("price") is not None:
            client.patch(f"/procedures/{proc_id}/positions/{pp['id']}", json={"price": src["price"]})
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r = client.post(f"/procedures/{proc_id}/to-support")
    assert r.status_code == 200, r.text
    return proc_id


def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def _delivery_upd(client, code, title, positions):
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


def _make_role_user(db, email, department, is_curator=False, global_role=None):
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name=email.split("@")[0], account_type="department" if department else "global",
        department=department, is_curator=1 if is_curator else 0, global_role=global_role,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login_as(client, email, password="userpass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


# --- 9.1 Task 1: shape / auth / validation -------------------------------------

def test_report_shape_and_keys(client_admin):
    r = client_admin.get("/reports/time")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"type", "title", "period", "kpis", "sections"}
    assert body["type"] == "time"


def test_report_unknown_type_404(client_admin):
    assert client_admin.get("/reports/bogus").status_code == 404


def test_report_unauth_401(client_seeded):
    assert client_seeded.get("/reports/time").status_code == 401


def test_report_must_change_403(client_seeded):
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    assert client_seeded.get("/reports/time").status_code == 403


def test_report_employee_forbidden_403(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "kompl_emp@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 403


def test_report_curator_ok(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "kompl_cur@crm.local", "Комплектация", is_curator=True)
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 200


def test_report_rukovoditel_ok(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "ruk@crm.local", None, global_role="Руководитель")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 200


def test_report_custom_period_validation_422(client_admin):
    # custom without range
    assert client_admin.get("/reports/time?period=custom").status_code == 422
    # custom inverted
    q = f"?period=custom&date_from={days_ago(1)}&date_to={days_ago(5)}"
    assert client_admin.get("/reports/time" + q).status_code == 422


def test_report_custom_period_ok(client_admin):
    q = f"?period=custom&date_from={days_ago(10)}&date_to={days_ago(0)}"
    r = client_admin.get("/reports/time" + q)
    assert r.status_code == 200
    # period.key echo is asserted in T3 once report_time returns a real period


def test_report_unknown_period_422(client_admin):
    assert client_admin.get("/reports/time?period=bogus").status_code == 422


def test_filters_shape(client_admin):
    r = client_admin.get("/reports")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"mtr", "supplier", "author"}
