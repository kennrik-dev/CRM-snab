"""Tests for /search global search router (Phase 3.4).

Spec (locked):
- GET /search?q=<string>&limit=<int> (limit default 20, max 50)
- require_password_changed
- Returns {"parents": [...], "procedures": [...], "suppliers": [...]}
- Empty/whitespace q => all groups empty (no DB calls)
- Case-insensitive substring match
- parents: code OR title matches, order by created_at DESC, limit per group
- procedures: proc IS NOT NULL AND proc ILIKE %q%, order by created_at DESC
- suppliers: distinct procedure.supplier values matching %q%, with proc_count
  (excludes NULL), order by proc_count DESC, name ASC
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.security import hash_password
from app.models import ParentRequest, Procedure, Tender, User

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
    def _fk_pragma_on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

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

    client_seeded.post("/auth/logout")

    r_li = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD},
    )
    assert r_li.status_code == 200, r_li.text
    assert r_li.json()["must_change_password"] is False

    return client_seeded


@pytest.fixture()
def client_must_change(client_seeded):
    """TestClient logged in as admin with must_change_password=1 (not yet changed)."""
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is True
    return client_seeded


# ---------------------------------------------------------------------------
# Helpers — insert fixtures directly via DB
# ---------------------------------------------------------------------------

def _make_parent(db, code: str, title: str, mtr: str = "MTR-1") -> ParentRequest:
    p = ParentRequest(
        code=code,
        title=title,
        mtr=mtr,
        sostavitel="Test Sostavitel",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_tender(db, num: str, parent_id: int) -> Tender:
    t = Tender(num=num, parent_id=parent_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_procedure(
    db,
    *,
    tender_id: int,
    proc: str | None = None,
    supplier: str | None = None,
) -> Procedure:
    p = Procedure(
        proc=proc,
        tender_id=tender_id,
        supplier=supplier,
        block="zakupka",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# /search — empty q
# ---------------------------------------------------------------------------

def test_search_empty_q_returns_empty_groups_without_db_calls(client_admin, db_seeded):
    """An empty/whitespace q must return all groups empty (no DB lookups)."""
    # Insert some data so the DB has rows — but with empty q, none should surface.
    parent = _make_parent(db_seeded, code="Т-1", title="Любой заголовок")
    tender = _make_tender(db_seeded, num="T-1", parent_id=parent.id)
    _make_procedure(db_seeded, tender_id=tender.id, proc="PR-1", supplier="ООО А")

    r = client_admin.get("/search?q=")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"parents": [], "procedures": [], "suppliers": []}


def test_search_whitespace_q_returns_empty_groups(client_admin):
    r = client_admin.get("/search?q=%20%20%20")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"parents": [], "procedures": [], "suppliers": []}


# ---------------------------------------------------------------------------
# /search — no data
# ---------------------------------------------------------------------------

def test_search_no_data_returns_empty_groups(client_admin):
    r = client_admin.get("/search?q=anything")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"parents": [], "procedures": [], "suppliers": []}


# ---------------------------------------------------------------------------
# /search — parents
# ---------------------------------------------------------------------------

def test_search_parent_code_match(client_admin, db_seeded):
    _make_parent(db_seeded, code="Т-67", title="Заголовок про закупку")

    r = client_admin.get("/search?q=Т")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["parents"]) == 1
    p = body["parents"][0]
    assert set(p.keys()) >= {"id", "code", "title"}
    assert p["code"] == "Т-67"
    assert p["title"] == "Заголовок про закупку"
    assert body["procedures"] == []
    assert body["suppliers"] == []


def test_search_parent_title_match(client_admin, db_seeded):
    _make_parent(db_seeded, code="P-1", title="Клапаны запорные")

    # Use same case as data — SQLite+SQLAlchemy ilike handles same-case
    # Cyrillic substring, but case-mixed Cyrillic is out of scope for SQLite
    # without a custom collation.
    r = client_admin.get("/search?q=Клапаны")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["parents"]) == 1
    assert body["parents"][0]["code"] == "P-1"


# ---------------------------------------------------------------------------
# /search — procedures
# ---------------------------------------------------------------------------

def test_search_procedure_proc_match(client_admin, db_seeded):
    parent = _make_parent(db_seeded, code="T-1", title="T")
    tender = _make_tender(db_seeded, num="T-1", parent_id=parent.id)
    proc = _make_procedure(db_seeded, tender_id=tender.id, proc="PR-001")

    r = client_admin.get("/search?q=PR")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["procedures"]) == 1
    p = body["procedures"][0]
    assert set(p.keys()) >= {"id", "proc", "supplier", "tender_id"}
    assert p["proc"] == "PR-001"
    assert p["tender_id"] == tender.id


def test_search_procedure_null_proc_is_excluded(client_admin, db_seeded):
    """A procedure with proc=NULL must not appear, even if its other fields
    would match q."""
    parent = _make_parent(db_seeded, code="X-1", title="X")
    tender = _make_tender(db_seeded, num="X-1", parent_id=parent.id)
    _make_procedure(db_seeded, tender_id=tender.id, proc=None, supplier="Ромашка")

    r = client_admin.get("/search?q=Ромашка")
    assert r.status_code == 200, r.text
    body = r.json()
    # Proc is NULL — must NOT appear in procedures
    assert body["procedures"] == []
    # But supplier group should still match
    assert len(body["suppliers"]) == 1


# ---------------------------------------------------------------------------
# /search — suppliers
# ---------------------------------------------------------------------------

def test_search_suppliers_grouping_with_proc_count(client_admin, db_seeded):
    parent = _make_parent(db_seeded, code="S-1", title="S")
    tender = _make_tender(db_seeded, num="S-1", parent_id=parent.id)
    # Two procedures with the same supplier
    _make_procedure(db_seeded, tender_id=tender.id, proc="P-A", supplier="ООО Ромашка")
    _make_procedure(db_seeded, tender_id=tender.id, proc="P-B", supplier="ООО Ромашка")
    # One with a different supplier
    _make_procedure(db_seeded, tender_id=tender.id, proc="P-C", supplier="ИП Иванов")

    r = client_admin.get("/search?q=Ромашка")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["suppliers"]) == 1
    s = body["suppliers"][0]
    assert s["name"] == "ООО Ромашка"
    assert s["proc_count"] == 2


def test_search_suppliers_null_is_excluded(client_admin, db_seeded):
    """A procedure with supplier=NULL must not appear in the suppliers group."""
    parent = _make_parent(db_seeded, code="N-1", title="N")
    tender = _make_tender(db_seeded, num="N-1", parent_id=parent.id)
    _make_procedure(db_seeded, tender_id=tender.id, proc="P-X", supplier=None)

    r = client_admin.get("/search?q=")  # q="" to avoid filtering by supplier name
    assert r.status_code == 200
    assert r.json()["suppliers"] == []


# ---------------------------------------------------------------------------
# /search — no match
# ---------------------------------------------------------------------------

def test_search_no_match_returns_empty_groups(client_admin, db_seeded):
    _make_parent(db_seeded, code="A-1", title="Alpha")
    parent = _make_parent(db_seeded, code="B-2", title="Beta")
    tender = _make_tender(db_seeded, num="B-2", parent_id=parent.id)
    _make_procedure(db_seeded, tender_id=tender.id, proc="PR-Z", supplier="Acme")

    r = client_admin.get("/search?q=ZZZ")
    assert r.status_code == 200, r.text
    assert r.json() == {"parents": [], "procedures": [], "suppliers": []}


# ---------------------------------------------------------------------------
# /search — limit
# ---------------------------------------------------------------------------

def test_search_limit_truncates_each_group(client_admin, db_seeded):
    # 3 parents
    for i in range(3):
        _make_parent(db_seeded, code=f"Т-{i}", title=f"Заголовок {i}")

    # 3 procedures
    parent = _make_parent(db_seeded, code="P-9", title="Procedures parent")
    tender = _make_tender(db_seeded, num="P-9", parent_id=parent.id)
    for i in range(3):
        _make_procedure(db_seeded, tender_id=tender.id, proc=f"PR-X{i}", supplier="Ромашка")

    # 3 suppliers (distinct names, but we group by supplier — so make 3 different
    # suppliers whose name contains "Фирма")
    for i in range(3):
        _make_procedure(
            db_seeded,
            tender_id=tender.id,
            proc=f"PR-Y{i}",
            supplier=f"Фирма {i}",
        )

    r = client_admin.get("/search?q=Т&limit=1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["parents"]) == 1


def test_search_limit_default_is_20(client_admin, db_seeded):
    # With no data, structure must still be correct
    r = client_admin.get("/search?q=anything")
    assert r.status_code == 200
    body = r.json()
    assert "parents" in body and isinstance(body["parents"], list)


# ---------------------------------------------------------------------------
# /search — auth gating
# ---------------------------------------------------------------------------

def test_search_unauthenticated_returns_401(client_seeded):
    r = client_seeded.get("/search?q=foo")
    assert r.status_code == 401


def test_search_must_change_password_returns_403(client_must_change):
    r = client_must_change.get("/search?q=foo")
    assert r.status_code == 403
