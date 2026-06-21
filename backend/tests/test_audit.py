"""Tests for audit helpers: write_audit + paginate + apply_archive_filter.

Phase 3.2 — locked spec.
"""
from __future__ import annotations

from typing import Optional

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit import apply_archive_filter, paginate, write_audit
from app.db import Base
from app.models import AuditLog, ParentRequest, User
from app.security import hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
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


def _make_user(db, *, email="actor@crm.local") -> User:
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name=email,
        account_type="global",
        department=None,
        is_curator=0,
        global_role="Админ",
        is_active=1,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# write_audit
# ---------------------------------------------------------------------------

def test_write_audit_with_user_appends_row_and_commits(db):
    actor = _make_user(db, email="actor1@crm.local")

    row = write_audit(db, entity_kind="parent", entity_id=42, user=actor, action="create")

    assert row.id is not None
    assert row.entity_kind == "parent"
    assert row.entity_id == 42
    assert row.user_id == actor.id
    assert row.action == "create"
    assert row.created_at  # populated by server_default

    # Must be persisted (commit was called)
    fresh = db.query(AuditLog).filter_by(id=row.id).one()
    assert fresh.user_id == actor.id


def test_write_audit_with_user_id_int_appends_row(db):
    actor = _make_user(db, email="actor2@crm.local")

    row = write_audit(db, entity_kind="procedure", entity_id=7, user=actor.id, action="edit")

    assert row.user_id == actor.id
    assert row.entity_kind == "procedure"
    assert row.entity_id == 7
    assert row.action == "edit"


def test_write_audit_returns_audit_log_instance(db):
    actor = _make_user(db, email="actor3@crm.local")
    row = write_audit(db, entity_kind="parent", entity_id=1, user=actor, action="view")
    assert isinstance(row, AuditLog)


# ---------------------------------------------------------------------------
# paginate
# ---------------------------------------------------------------------------

def _make_request(db, code: str, status: str = "awaiting") -> ParentRequest:
    pr = ParentRequest(
        code=code,
        title=f"Title for {code}",
        mtr="MTR-1",
        srok="2026-01-01",
        sostavitel="Test",
        dept="Закупки",
        status=status,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr


def test_paginate_returns_total_and_first_page(db):
    for i in range(7):
        _make_request(db, f"PR-{i:03d}")

    q = db.query(ParentRequest).order_by(ParentRequest.id)
    result = paginate(q, page=1, page_size=3)

    assert result["total"] == 7
    assert len(result["items"]) == 3
    assert [it.code for it in result["items"]] == ["PR-000", "PR-001", "PR-002"]


def test_paginate_second_page_offset_correctly(db):
    for i in range(7):
        _make_request(db, f"PR-{i:03d}")

    q = db.query(ParentRequest).order_by(ParentRequest.id)
    result = paginate(q, page=2, page_size=3)

    assert result["total"] == 7
    assert len(result["items"]) == 3
    assert [it.code for it in result["items"]] == ["PR-003", "PR-004", "PR-005"]


def test_paginate_last_page_partial(db):
    for i in range(7):
        _make_request(db, f"PR-{i:03d}")

    q = db.query(ParentRequest).order_by(ParentRequest.id)
    result = paginate(q, page=3, page_size=3)

    assert result["total"] == 7
    assert len(result["items"]) == 1
    assert result["items"][0].code == "PR-006"


def test_paginate_empty(db):
    q = db.query(ParentRequest).order_by(ParentRequest.id)
    result = paginate(q, page=1, page_size=50)

    assert result["total"] == 0
    assert result["items"] == []


def test_paginate_default_page_size(db):
    for i in range(60):
        _make_request(db, f"PR-{i:03d}")

    q = db.query(ParentRequest).order_by(ParentRequest.id)
    result = paginate(q, page=1)  # default page_size=50

    assert result["total"] == 60
    assert len(result["items"]) == 50


# ---------------------------------------------------------------------------
# apply_archive_filter
# ---------------------------------------------------------------------------

def test_apply_archive_filter_false_excludes_cancelled(db):
    _make_request(db, "PR-A", status="awaiting")
    _make_request(db, "PR-B", status="awaiting")
    _make_request(db, "PR-C", status="cancelled")

    q = apply_archive_filter(db.query(ParentRequest).order_by(ParentRequest.id), False)
    rows = q.all()

    assert len(rows) == 2
    assert {r.code for r in rows} == {"PR-A", "PR-B"}


def test_apply_archive_filter_true_keeps_cancelled(db):
    _make_request(db, "PR-A", status="awaiting")
    _make_request(db, "PR-B", status="awaiting")
    _make_request(db, "PR-C", status="cancelled")

    q = apply_archive_filter(db.query(ParentRequest).order_by(ParentRequest.id), True)
    rows = q.all()

    assert len(rows) == 3
    assert {r.code for r in rows} == {"PR-A", "PR-B", "PR-C"}


def test_apply_archive_filter_default_excludes_cancelled(db):
    """Default behavior: include_archived=False (most recent live data)."""
    _make_request(db, "PR-A", status="awaiting")
    _make_request(db, "PR-B", status="cancelled")

    q = apply_archive_filter(db.query(ParentRequest).order_by(ParentRequest.id))
    rows = q.all()

    assert len(rows) == 1
    assert rows[0].code == "PR-A"
