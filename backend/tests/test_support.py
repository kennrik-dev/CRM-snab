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


# --- 6.2b: GET /support list ----------------------------------------------------

def test_support_list_empty(client_admin):
    r = client_admin.get("/support")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


def test_support_list_shows_support_procedure_with_derived(client_admin):
    proc_id = _to_support(client_admin, "SUP-L1", "list one",
                          [{"name": "x", "qty": 10.0}])
    # set srok_dd in the past + not delivered → is_overdue True, overdue_pct by deliveries
    client_admin.patch(f"/procedures/{proc_id}", json={"srok_dd": "2026-06-01"})
    r = client_admin.get("/support")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == proc_id
    assert item["code"] == "SUP-L1"
    assert item["status_postavki"] == "Новая"
    assert item["is_overdue"] is True          # srok passed, not Поставлено
    assert item["overdue_pct"] == 0.0          # no deliveries → 0
    assert item["docs"] == {"ttn": False, "m15": False, "upd": False, "sert": False}
    assert item["progress_delivered"] == 0
    assert item["progress_total"] == 1


def test_support_list_excludes_zakupka_block(client_admin, db_seeded):
    from app.models import ParentRequest, Tender, Procedure
    pr = ParentRequest(code="ZK-ONLY", title="zk", sostavitel="X", status="awaiting")
    db_seeded.add(pr); db_seeded.commit(); db_seeded.refresh(pr)
    t = Tender(parent_id=pr.id); db_seeded.add(t); db_seeded.commit(); db_seeded.refresh(t)
    db_seeded.add(Procedure(tender_id=t.id, block="zakupka")); db_seeded.commit()
    r = client_admin.get("/support")
    assert r.json()["total"] == 0


def test_support_list_cancelled_hidden_by_default(client_admin):
    proc_id = _to_support(client_admin, "SUP-CXL", "cancel",
                          [{"name": "x", "qty": 1.0}])
    client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Отменена"})
    assert proc_id not in {it["id"] for it in client_admin.get("/support").json()["items"]}
    assert proc_id in {it["id"] for it in client_admin.get("/support?include_archived=1").json()["items"]}


def test_support_list_pagination(client_admin):
    for i in range(3):
        _to_support(client_admin, f"SUP-PG{i}", f"pg{i}", [{"name": "x", "qty": 1.0}])
    r1 = client_admin.get("/support?page=1&page_size=2")
    assert r1.json()["total"] == 3
    assert len(r1.json()["items"]) == 2
    r2 = client_admin.get("/support?page=2&page_size=2")
    assert len(r2.json()["items"]) == 1


# --- 6.2c: POST deliveries ------------------------------------------------------

def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def test_create_delivery_happy(client_admin):
    proc_id = _to_support(client_admin, "DLV-1", "delivery",
                          [{"name": "A", "qty": 10.0}, {"name": "B", "qty": 5.0}])
    pids = _position_ids(client_admin, proc_id)
    r = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pids[0]]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "transit"
    assert d["n"] == 1
    assert d["upd"] is None
    # position now assigned (delivery_id set) — visible in detail
    det = client_admin.get(f"/procedures/{proc_id}").json()
    assert len(det["deliveries"]) == 1
    assigned = {p["delivery_id"] for p in det["positions"]}
    assert d["id"] in assigned


def test_create_delivery_empty_422(client_admin):
    proc_id = _to_support(client_admin, "DLV-EMPTY", "empty", [{"name": "x", "qty": 1.0}])
    r = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": []})
    assert r.status_code == 422


def test_create_delivery_position_already_assigned_422(client_admin):
    proc_id = _to_support(client_admin, "DLV-DUP", "dup", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]})
    r = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]})
    assert r.status_code == 422


def test_create_delivery_two_sequences_n(client_admin):
    proc_id = _to_support(client_admin, "DLV-N", "seq",
                          [{"name": "A", "qty": 1.0}, {"name": "B", "qty": 1.0}])
    pids = _position_ids(client_admin, proc_id)
    d1 = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pids[0]]}).json()
    d2 = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pids[1]]}).json()
    assert d1["n"] == 1 and d2["n"] == 2


def test_create_delivery_other_procedure_position_404(client_admin):
    a = _to_support(client_admin, "DLV-A", "a", [{"name": "x", "qty": 1.0}])
    b = _to_support(client_admin, "DLV-B", "b", [{"name": "y", "qty": 1.0}])
    pid_b = _position_ids(client_admin, b)[0]
    r = client_admin.post(f"/procedures/{a}/deliveries", json={"positions": [pid_b]})
    assert r.status_code == 404


# --- 6.2d: DELETE delivery ------------------------------------------------------

def test_delete_delivery_transit_returns_positions(client_admin):
    proc_id = _to_support(client_admin, "DEL-1", "del", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.delete(f"/deliveries/{d['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # position back to awaiting
    pos = client_admin.get(f"/procedures/{proc_id}").json()["positions"][0]
    assert pos["delivery_id"] is None
    assert client_admin.get(f"/procedures/{proc_id}").json()["deliveries"] == []


def test_delete_delivery_done_409(client_admin):
    proc_id = _to_support(client_admin, "DEL-DONE", "done", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    client_admin.patch(f"/deliveries/{d['id']}", json={"status": "done"})  # transit→done
    r = client_admin.delete(f"/deliveries/{d['id']}")
    assert r.status_code == 409


def test_delete_delivery_with_upd_409(client_admin):
    proc_id = _to_support(client_admin, "DEL-UPD", "upd", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    client_admin.post(f"/deliveries/{d['id']}/upd", json={"upd": "UPD-99"})
    r = client_admin.delete(f"/deliveries/{d['id']}")
    assert r.status_code == 409


def test_delete_delivery_not_found_404(client_admin):
    assert client_admin.delete("/deliveries/99999").status_code == 404
