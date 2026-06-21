from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import Base, engine
from app import models  # noqa: F401  -- ensure models are registered

EXPECTED_TABLES = {
    "user",
    "parent_request",
    "requested_position",
    "tender",
    "procedure",
    "delivery",
    "procedure_position",
    "upd_payment",
    "upd_position",
    "comment",
    "audit_log",
    "dict",
}


def test_all_twelve_tables_exist(db):
    inspector = inspect(db.get_bind())
    actual = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - actual
    assert not missing, f"missing tables: {missing}"


def test_procedure_block_check_rejects_invalid(db):
    from app.models import Procedure

    p = Procedure(tender_id=1, block="foo")
    db.add(p)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_upd_payment_pay_status_check_rejects_invalid(db):
    from app.models import UpdPayment

    u = UpdPayment(upd="X-1", origin="manual", pay_status="late")
    db.add(u)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_delivery_status_check_rejects_invalid(db):
    from app.models import Delivery

    d = Delivery(procedure_id=1, n=1, status="late")
    db.add(d)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_requested_position_fk_enforced(db):
    from app.models import RequestedPosition

    rp = RequestedPosition(parent_id=99999, name="x", qty=1)
    db.add(rp)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_email_unique(db):
    from app.models import User

    u1 = User(
        email="a@b.local",
        password_hash="x",
        full_name="A",
        account_type="global",
    )
    db.add(u1)
    db.commit()

    u2 = User(
        email="a@b.local",
        password_hash="y",
        full_name="B",
        account_type="global",
    )
    db.add(u2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_index_ix_proc_block_exists(db):
    inspector = inspect(db.get_bind())
    indexes = inspector.get_indexes("procedure")
    names = {i["name"] for i in indexes}
    assert "ix_proc_block" in names


def test_parent_request_roundtrip(db):
    from app.models import ParentRequest

    p = ParentRequest(
        code="Т-67",
        title="Test",
        sostavitel="Иванов",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    found = db.query(ParentRequest).filter_by(code="Т-67").one()
    assert found.id == p.id
    assert found.code == "Т-67"
    assert found.title == "Test"


def test_procedure_tender_relationship(db):
    from app.models import ParentRequest, Tender, Procedure

    pr = ParentRequest(code="Т-1", title="P", sostavitel="X")
    db.add(pr)
    db.commit()
    db.refresh(pr)

    t = Tender(parent_id=pr.id)
    db.add(t)
    db.commit()
    db.refresh(t)

    proc = Procedure(tender_id=t.id)
    db.add(proc)
    db.commit()
    db.refresh(proc)

    assert proc.tender is not None
    assert proc.tender.id == t.id
    assert proc.tender.parent_id == pr.id


def test_audit_log_roundtrip(db):
    from app.models import AuditLog

    a = AuditLog(entity_kind="procedure", entity_id=1, action="create")
    db.add(a)
    db.commit()
    db.refresh(a)

    found = db.query(AuditLog).filter_by(entity_kind="procedure").one()
    assert found.id == a.id
    assert found.action == "create"
    assert found.created_at is not None
