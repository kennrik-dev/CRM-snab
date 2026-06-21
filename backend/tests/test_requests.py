"""Tests for /requests router: parent_request CRUD + positions mass insert.

Phase 4.1 — locked spec from `docs/31-api.md` §2 and `docs/02-statuses.md` §7.1.
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


# ---------------------------------------------------------------------------
# Helpers to create users via DB
# ---------------------------------------------------------------------------

def _make_kompl_emp(db, email="kompl_emp@crm.local", full_name="Комплектовщик Тестовый"):
    """Department user (Комплектация, employee) — has komplektaciya edit rights."""
    from app.models import User
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name=full_name,
        account_type="department",
        department="Комплектация",
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_kompl_emp_with_must_change(db, email="kompl_must@crm.local"):
    """Department user (Комплектация, employee) with must_change_password=1."""
    from app.models import User
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name="Комплектовщик ДолженСменить",
        account_type="department",
        department="Комплектация",
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=1,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_zakup_emp(db, email="zakup_emp@crm.local"):
    """Закупки employee — has NO komplektaciya edit rights."""
    from app.models import User
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name="Закупщик Тестовый",
        account_type="department",
        department="Закупки",
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _login_as(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r


def _create_request_via_api(
    client,
    code="Т-001",
    title="Тестовая заявка",
    mtr=None,
    srok=None,
    dept=None,
    positions=None,
):
    """Helper to create a request via the API. Returns the response JSON."""
    payload = {
        "code": code,
        "title": title,
        "mtr": mtr,
        "srok": srok,
        "dept": dept,
        "positions": positions if positions is not None else [],
    }
    r = client.post("/requests", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ===========================================================================
# POST /requests
# ===========================================================================

def test_create_request_as_admin_200(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="Т-001",
        title="Тест",
        positions=[{"name": "Болт", "qty": 10.0, "unit": "шт"}],
    )
    assert "id" in body
    assert body["code"] == "Т-001"
    assert body["title"] == "Тест"
    assert body["status"] == "awaiting"
    assert isinstance(body["positions"], list)
    assert len(body["positions"]) == 1
    assert body["positions"][0]["name"] == "Болт"


def test_create_request_persists_positions(client_admin, db_seeded):
    body = _create_request_via_api(
        client_admin,
        code="Т-PERS",
        title="Persist Test",
        positions=[
            {"name": "Гайка", "qty": 5.0, "unit": "шт"},
            {"name": "Шайба", "qty": 20.0, "unit": "шт"},
        ],
    )
    req_id = body["id"]

    # GET it back
    r = client_admin.get(f"/requests/{req_id}")
    assert r.status_code == 200
    got = r.json()
    assert len(got["positions"]) == 2
    names = {p["name"] for p in got["positions"]}
    assert names == {"Гайка", "Шайба"}


def test_create_request_duplicate_code_409(client_admin):
    _create_request_via_api(client_admin, code="DUP-1", title="Первый")
    r = client_admin.post(
        "/requests",
        json={"code": "DUP-1", "title": "Второй", "positions": []},
    )
    assert r.status_code == 409


def test_create_request_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    r = client_seeded.post(
        "/requests",
        json={"code": "X-1", "title": "Чужой", "positions": []},
    )
    assert r.status_code == 403


def test_create_request_unauthenticated_401(client_seeded):
    r = client_seeded.post(
        "/requests",
        json={"code": "X-1", "title": "Чужой", "positions": []},
    )
    assert r.status_code == 401


def test_create_request_must_change_password_403(client_seeded, db_seeded):
    u = _make_kompl_emp_with_must_change(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    r = client_seeded.post(
        "/requests",
        json={"code": "X-2", "title": "Чужой", "positions": []},
    )
    assert r.status_code == 403


def test_create_request_empty_positions_200_position_count_zero(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="EMPTY-1",
        title="Без позиций",
        positions=[],
    )
    assert body["positions"] == []

    # list endpoint should show position_count=0
    r = client_admin.get("/requests")
    items = r.json()["items"]
    target = next(it for it in items if it["code"] == "EMPTY-1")
    assert target["position_count"] == 0


def test_create_request_audit_create_written(client_admin, db_seeded):
    from app.models import AuditLog

    body = _create_request_via_api(client_admin, code="AUDIT-1", title="Аудит")
    req_id = body["id"]

    db_seeded.expire_all()
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=req_id, action="create")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id is not None


# ===========================================================================
# GET /requests
# ===========================================================================

def test_list_requests_returns_paginated(client_admin):
    _create_request_via_api(client_admin, code="L-1", title="один")
    _create_request_via_api(client_admin, code="L-2", title="два")

    r = client_admin.get("/requests")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 2


def test_list_excludes_parents_with_procedures(client_admin, db_seeded):
    from app.models import Tender

    # Parent A — no tender (should appear in list)
    parent_a = _create_request_via_api(client_admin, code="LIST-A", title="Без торга")

    # Parent B — with tender (should NOT appear in list by default)
    parent_b = _create_request_via_api(client_admin, code="LIST-B", title="С торгов")
    db_seeded.add(Tender(parent_id=parent_b["id"]))
    db_seeded.commit()

    r = client_admin.get("/requests")
    items = r.json()["items"]
    codes = {it["code"] for it in items}
    assert "LIST-A" in codes
    assert "LIST-B" not in codes


def test_list_include_archived_includes_cancelled(client_admin):
    _create_request_via_api(client_admin, code="ARCH-A", title="Активная")
    body_b = _create_request_via_api(client_admin, code="ARCH-B", title="Отменяемая")
    r = client_admin.post(f"/requests/{body_b['id']}/cancel")
    assert r.status_code == 200

    r = client_admin.get("/requests")
    codes = {it["code"] for it in r.json()["items"]}
    assert "ARCH-A" in codes
    assert "ARCH-B" not in codes

    r2 = client_admin.get("/requests?include_archived=1")
    codes2 = {it["code"] for it in r2.json()["items"]}
    assert "ARCH-A" in codes2
    assert "ARCH-B" in codes2


def test_list_status_filter_cancelled(client_admin):
    body_a = _create_request_via_api(client_admin, code="ST-A", title="Актив")
    body_b = _create_request_via_api(client_admin, code="ST-B", title="Отмен")
    client_admin.post(f"/requests/{body_b['id']}/cancel")

    r = client_admin.get("/requests?status=cancelled")
    codes = {it["code"] for it in r.json()["items"]}
    assert codes == {"ST-B"}


def test_list_search_case_insensitive_cyrillic(client_admin):
    _create_request_via_api(client_admin, code="ПОИСК-X", title="Раз")
    _create_request_via_api(client_admin, code="OTHER-1", title="Поиск-в-title")

    # search by code fragment (lowercase)
    r1 = client_admin.get("/requests?search=поиск")
    codes1 = {it["code"] for it in r1.json()["items"]}
    assert "ПОИСК-X" in codes1
    assert "OTHER-1" in codes1

    # search that matches only title
    r2 = client_admin.get("/requests?search=Поиск-в-title")
    codes2 = {it["code"] for it in r2.json()["items"]}
    assert "OTHER-1" in codes2


def test_list_sort_by_code_asc(client_admin):
    _create_request_via_api(client_admin, code="ZZZ", title="ззз")
    _create_request_via_api(client_admin, code="AAA", title="ааа")

    r = client_admin.get("/requests?sort=code")
    items = r.json()["items"]
    codes = [it["code"] for it in items]
    # AAA should come before ZZZ
    a_idx = codes.index("AAA")
    z_idx = codes.index("ZZZ")
    assert a_idx < z_idx


def test_list_default_sort_created_at_desc(client_admin):
    body1 = _create_request_via_api(client_admin, code="DT-1", title="один")
    body2 = _create_request_via_api(client_admin, code="DT-2", title="два")

    r = client_admin.get("/requests")
    items = r.json()["items"]
    # the most recently created should be first
    # we can check both exist; DT-2 created after DT-1
    codes = [it["code"] for it in items]
    # find their relative order
    i1 = codes.index("DT-1")
    i2 = codes.index("DT-2")
    # DT-2 should come before DT-1 (created later)
    assert i2 < i1


def test_list_pagination_page2_page_size_1(client_admin):
    _create_request_via_api(client_admin, code="PG-A", title="а")
    _create_request_via_api(client_admin, code="PG-B", title="б")
    _create_request_via_api(client_admin, code="PG-C", title="в")

    r1 = client_admin.get("/requests?page=1&page_size=1")
    assert r1.json()["total"] >= 3
    assert len(r1.json()["items"]) == 1

    r2 = client_admin.get("/requests?page=2&page_size=1")
    assert len(r2.json()["items"]) == 1
    assert r1.json()["items"][0]["code"] != r2.json()["items"][0]["code"]


def test_list_page_size_too_large_422(client_admin):
    r = client_admin.get("/requests?page_size=300")
    assert r.status_code == 422


# ===========================================================================
# GET /requests/{id}
# ===========================================================================

def test_get_request_by_id_found(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="GET-1",
        title="Детально",
        positions=[{"name": "Позиция", "qty": 1.0}],
    )
    r = client_admin.get(f"/requests/{body['id']}")
    assert r.status_code == 200
    got = r.json()
    assert got["id"] == body["id"]
    assert got["code"] == "GET-1"
    assert len(got["positions"]) == 1
    assert got["tenders"] == []


def test_get_request_by_id_with_tenders_and_procedures(client_admin, db_seeded):
    from app.models import Tender, Procedure

    body = _create_request_via_api(client_admin, code="GET-T", title="С торгами")
    t = Tender(parent_id=body["id"])
    db_seeded.add(t)
    db_seeded.commit()
    db_seeded.refresh(t)
    p = Procedure(tender_id=t.id, block="zakupka")
    db_seeded.add(p)
    db_seeded.commit()

    r = client_admin.get(f"/requests/{body['id']}")
    assert r.status_code == 200
    got = r.json()
    assert len(got["tenders"]) == 1
    assert got["tenders"][0]["id"] == t.id
    assert len(got["tenders"][0]["procedures"]) == 1


def test_get_request_not_found_404(client_admin):
    r = client_admin.get("/requests/99999")
    assert r.status_code == 404


# ===========================================================================
# PATCH /requests/{id}
# ===========================================================================

def test_patch_request_awaiting_updates_fields(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="PT-1",
        title="Старое название",
        mtr="M1",
    )
    r = client_admin.patch(
        f"/requests/{body['id']}",
        json={"title": "Новое название", "mtr": "M2"},
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["title"] == "Новое название"
    assert got["mtr"] == "M2"


def test_patch_request_cancelled_409(client_admin):
    body = _create_request_via_api(client_admin, code="PT-2", title="Будет отменена")
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.patch(
        f"/requests/{body['id']}",
        json={"title": "Нельзя"},
    )
    assert r.status_code == 409


def test_patch_request_partial_only_mtr(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="PT-3",
        title="Изначальное",
        mtr="MTR-orig",
        srok="2026-01-01",
    )
    r = client_admin.patch(
        f"/requests/{body['id']}",
        json={"mtr": "MTR-new"},
    )
    assert r.status_code == 200
    got = r.json()
    assert got["mtr"] == "MTR-new"
    assert got["title"] == "Изначальное"
    assert got["srok"] == "2026-01-01"


def test_patch_request_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    # create a request via DB directly (no komplektaciya needed at DB level)
    from app.models import ParentRequest
    pr = ParentRequest(
        code="PT-Z",
        title="Test",
        mtr="M",
        sostavitel="X",
        status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)

    r = client_seeded.patch(
        f"/requests/{pr.id}",
        json={"title": "Попытка"},
    )
    assert r.status_code == 403


def test_patch_request_audit_update_written(client_admin, db_seeded):
    from app.models import AuditLog

    body = _create_request_via_api(client_admin, code="PT-AUD", title="Аудит")
    client_admin.patch(
        f"/requests/{body['id']}",
        json={"title": "Изменено"},
    )

    db_seeded.expire_all()
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=body["id"], action="update")
        .all()
    )
    assert len(rows) == 1


# ===========================================================================
# POST /requests/{id}/cancel
# ===========================================================================

def test_cancel_request_awaiting(client_admin):
    body = _create_request_via_api(client_admin, code="C-1", title="К отмене")
    r = client_admin.post(f"/requests/{body['id']}/cancel")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_cancel_request_already_cancelled_409(client_admin):
    body = _create_request_via_api(client_admin, code="C-2", title="Двойная отмена")
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.post(f"/requests/{body['id']}/cancel")
    assert r.status_code == 409


def test_cancel_request_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    from app.models import ParentRequest
    pr = ParentRequest(
        code="C-Z",
        title="X",
        sostavitel="Y",
        status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)

    r = client_seeded.post(f"/requests/{pr.id}/cancel")
    assert r.status_code == 403


def test_cancel_request_audit_written(client_admin, db_seeded):
    from app.models import AuditLog

    body = _create_request_via_api(client_admin, code="C-AUD", title="Аудит отмена")
    client_admin.post(f"/requests/{body['id']}/cancel")

    db_seeded.expire_all()
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=body["id"], action="cancel")
        .all()
    )
    assert len(rows) == 1


# ===========================================================================
# POST /requests/{id}/uncancel
# ===========================================================================

def test_uncancel_request_cancelled(client_admin):
    body = _create_request_via_api(client_admin, code="U-1", title="Восстановить")
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.post(f"/requests/{body['id']}/uncancel")
    assert r.status_code == 200
    assert r.json()["status"] == "awaiting"


def test_uncancel_request_awaiting_409(client_admin):
    body = _create_request_via_api(client_admin, code="U-2", title="Не отменена")
    r = client_admin.post(f"/requests/{body['id']}/uncancel")
    assert r.status_code == 409


def test_uncancel_request_audit_written(client_admin, db_seeded):
    from app.models import AuditLog

    body = _create_request_via_api(client_admin, code="U-AUD", title="Аудит восстановление")
    client_admin.post(f"/requests/{body['id']}/cancel")
    client_admin.post(f"/requests/{body['id']}/uncancel")

    db_seeded.expire_all()
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=body["id"], action="uncancel")
        .all()
    )
    assert len(rows) == 1


# ===========================================================================
# POST /requests/{id}/duplicate
# ===========================================================================

def test_duplicate_request_creates_copy(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="D-SRC",
        title="Оригинал",
        mtr="MTR-X",
        srok="2026-12-31",
        dept="Комплектация",
        positions=[
            {"name": "Болт", "qty": 10.0, "unit": "шт"},
            {"name": "Гайка", "qty": 5.0, "unit": "шт"},
        ],
    )
    r = client_admin.post(
        f"/requests/{body['id']}/duplicate",
        json={"code": "D-COPY"},
    )
    assert r.status_code == 200, r.text
    new_req = r.json()
    assert new_req["id"] != body["id"]
    assert new_req["code"] == "D-COPY"
    assert new_req["title"] == "Оригинал"
    assert new_req["mtr"] == "MTR-X"
    assert new_req["srok"] == "2026-12-31"
    assert new_req["dept"] == "Комплектация"
    assert new_req["status"] == "awaiting"
    assert len(new_req["positions"]) == 2


def test_duplicate_request_duplicate_code_409(client_admin):
    body1 = _create_request_via_api(client_admin, code="D-EXISTS", title="Оригинал")
    body2 = _create_request_via_api(client_admin, code="D-NEW", title="Копия")

    # try to duplicate body2 with body1's existing code
    r = client_admin.post(
        f"/requests/{body2['id']}/duplicate",
        json={"code": "D-EXISTS"},
    )
    assert r.status_code == 409


def test_duplicate_request_cancelled_409(client_admin):
    body = _create_request_via_api(client_admin, code="D-CXL", title="Отменяемая")
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.post(
        f"/requests/{body['id']}/duplicate",
        json={"code": "D-CXL-COPY"},
    )
    assert r.status_code == 409


def test_duplicate_request_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    from app.models import ParentRequest
    pr = ParentRequest(
        code="D-Z",
        title="Test",
        sostavitel="X",
        status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)

    r = client_seeded.post(
        f"/requests/{pr.id}/duplicate",
        json={"code": "D-Z-COPY"},
    )
    assert r.status_code == 403


def test_duplicate_request_positions_copied(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="D-POS",
        title="С позициями",
        positions=[
            {"name": "Болт", "qty": 10.0},
            {"name": "Гайка", "qty": 20.0},
            {"name": "Шайба", "qty": 30.0},
        ],
    )
    r = client_admin.post(
        f"/requests/{body['id']}/duplicate",
        json={"code": "D-POS-COPY"},
    )
    assert r.status_code == 200
    new_req = r.json()
    assert len(new_req["positions"]) == 3
    src_names = sorted(p["name"] for p in body["positions"])
    new_names = sorted(p["name"] for p in new_req["positions"])
    assert src_names == new_names


def test_duplicate_request_audit_written_on_new(client_admin, db_seeded):
    from app.models import AuditLog

    body = _create_request_via_api(client_admin, code="D-AUD", title="Аудит копия")
    r = client_admin.post(
        f"/requests/{body['id']}/duplicate",
        json={"code": "D-AUD-COPY"},
    )
    new_id = r.json()["id"]

    db_seeded.expire_all()
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=new_id, action="duplicate")
        .all()
    )
    assert len(rows) == 1


# ===========================================================================
# GET /requests/{id}/positions
# ===========================================================================

def test_list_positions_found(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="POS-1",
        title="С позициями",
        positions=[
            {"name": "Болт", "qty": 5.0},
            {"name": "Гайка", "qty": 10.0},
        ],
    )
    r = client_admin.get(f"/requests/{body['id']}/positions")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2


def test_list_positions_request_not_found_404(client_admin):
    r = client_admin.get("/requests/99999/positions")
    assert r.status_code == 404


# ===========================================================================
# POST /requests/{id}/positions (mass insert)
# ===========================================================================

def test_mass_insert_positions(client_admin):
    body = _create_request_via_api(client_admin, code="MI-1", title="Массовая вставка")

    new_positions = [
        {"name": "Болт", "qty": 10.0, "unit": "шт"},
        {"name": "Гайка", "qty": 20.0, "unit": "шт"},
        {"name": "Шайба", "qty": 30.0, "unit": "шт"},
    ]
    r = client_admin.post(
        f"/requests/{body['id']}/positions",
        json=new_positions,
    )
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 3

    # verify position_count increased
    r2 = client_admin.get("/requests")
    target = next(it for it in r2.json()["items"] if it["id"] == body["id"])
    assert target["position_count"] == 3


def test_mass_insert_empty_list(client_admin):
    body = _create_request_via_api(client_admin, code="MI-2", title="Пустая вставка")
    r = client_admin.post(f"/requests/{body['id']}/positions", json=[])
    assert r.status_code == 200
    assert r.json() == []


def test_mass_insert_cancelled_request_409(client_admin):
    body = _create_request_via_api(client_admin, code="MI-3", title="Отменяемая")
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.post(
        f"/requests/{body['id']}/positions",
        json=[{"name": "X", "qty": 1.0}],
    )
    assert r.status_code == 409


def test_mass_insert_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    from app.models import ParentRequest
    pr = ParentRequest(
        code="MI-Z",
        title="Test",
        sostavitel="X",
        status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)

    r = client_seeded.post(
        f"/requests/{pr.id}/positions",
        json=[{"name": "X", "qty": 1.0}],
    )
    assert r.status_code == 403


def test_mass_insert_audit_written(client_admin, db_seeded):
    from app.models import AuditLog

    body = _create_request_via_api(client_admin, code="MI-AUD", title="Аудит массовая")
    client_admin.post(
        f"/requests/{body['id']}/positions",
        json=[
            {"name": "A", "qty": 1.0},
            {"name": "B", "qty": 2.0},
        ],
    )

    db_seeded.expire_all()
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=body["id"], action="positions_add")
        .all()
    )
    assert len(rows) == 1


# ===========================================================================
# PATCH /requests/{id}/positions/{pos_id}
# ===========================================================================

def test_patch_position_awaiting(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="PP-1",
        title="Правка позиции",
        positions=[{"name": "Болт", "qty": 5.0}],
    )
    pos_id = body["positions"][0]["id"]

    r = client_admin.patch(
        f"/requests/{body['id']}/positions/{pos_id}",
        json={"name": "Болт новый", "qty": 10.0},
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["name"] == "Болт новый"
    assert got["qty"] == 10.0


def test_patch_position_not_found_404(client_admin):
    body = _create_request_via_api(client_admin, code="PP-2", title="Test")
    r = client_admin.patch(
        f"/requests/{body['id']}/positions/99999",
        json={"name": "X"},
    )
    assert r.status_code == 404


def test_patch_position_cancelled_409(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="PP-3",
        title="Отменяемая",
        positions=[{"name": "Болт", "qty": 5.0}],
    )
    pos_id = body["positions"][0]["id"]
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.patch(
        f"/requests/{body['id']}/positions/{pos_id}",
        json={"name": "X"},
    )
    assert r.status_code == 409


def test_patch_position_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    from app.models import ParentRequest, RequestedPosition
    pr = ParentRequest(
        code="PP-Z",
        title="Test",
        sostavitel="X",
        status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)

    pos = RequestedPosition(parent_id=pr.id, name="Болт", qty=1.0)
    db_seeded.add(pos)
    db_seeded.commit()
    db_seeded.refresh(pos)

    r = client_seeded.patch(
        f"/requests/{pr.id}/positions/{pos.id}",
        json={"name": "X"},
    )
    assert r.status_code == 403


# ===========================================================================
# DELETE /requests/{id}/positions/{pos_id}
# ===========================================================================

def test_delete_position_awaiting(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="DP-1",
        title="Удаление",
        positions=[{"name": "Болт", "qty": 5.0}],
    )
    pos_id = body["positions"][0]["id"]

    r = client_admin.delete(f"/requests/{body['id']}/positions/{pos_id}")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # verify gone
    r2 = client_admin.get(f"/requests/{body['id']}/positions")
    assert len(r2.json()) == 0


def test_delete_position_not_found_404(client_admin):
    body = _create_request_via_api(client_admin, code="DP-2", title="Test")
    r = client_admin.delete(f"/requests/{body['id']}/positions/99999")
    assert r.status_code == 404


def test_delete_position_cancelled_409(client_admin):
    body = _create_request_via_api(
        client_admin,
        code="DP-3",
        title="Отменяемая",
        positions=[{"name": "Болт", "qty": 5.0}],
    )
    pos_id = body["positions"][0]["id"]
    client_admin.post(f"/requests/{body['id']}/cancel")

    r = client_admin.delete(f"/requests/{body['id']}/positions/{pos_id}")
    assert r.status_code == 409


def test_delete_position_as_zakup_emp_403(client_seeded, db_seeded):
    u = _make_zakup_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")

    from app.models import ParentRequest, RequestedPosition
    pr = ParentRequest(
        code="DP-Z",
        title="Test",
        sostavitel="X",
        status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)

    pos = RequestedPosition(parent_id=pr.id, name="Болт", qty=1.0)
    db_seeded.add(pos)
    db_seeded.commit()
    db_seeded.refresh(pos)

    r = client_seeded.delete(f"/requests/{pr.id}/positions/{pos.id}")
    assert r.status_code == 403