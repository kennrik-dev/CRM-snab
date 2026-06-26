"""/payments router (Phase 7.1) — реестр УПД, ручное создание, карточка,
редактирование, «Провести оплату», сводка.

RBAC: мутации — require_action('soprovozhdenie','edit'); чтение — require_password_changed.
Audit: entity_kind='upd_payment'. Spec: docs/31-api.md §5, docs/32 §7.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import calculations as calc
from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import (
    Delivery,
    ParentRequest,
    Procedure,
    Tender,
    UpdPayment,
    UpdPosition,
    User,
)
from app.permissions import require_action
from app.schemas.payments import (
    PaginatedPayments,
    PaymentCreate,
    PaymentDetail,
    PaymentDeliveryOut,
    PaymentListItem,
    UpdPositionOut,
)


router = APIRouter(prefix="/payments", tags=["payments"])

_SORT_KEYS = {
    "created_at", "upd", "request", "supplier", "contract",
    "zrds", "status", "srok", "amount",
}


def _not_cancelled():
    """WHERE clause: procedure is absent (manual УПД) OR not 'Отменена'."""
    return or_(
        Procedure.status_postavki.is_(None),
        Procedure.status_postavki != "Отменена",
    )


@router.get("", response_model=PaginatedPayments)
def list_payments(
    search: Optional[str] = Query(None),
    hide_paid: bool = Query(False, description="Скрыть оплаченные"),
    sort: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaginatedPayments:
    q = (
        db.query(UpdPayment, ParentRequest.code, Delivery.n)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id, isouter=True)
        .join(Procedure, Delivery.procedure_id == Procedure.id, isouter=True)
        .join(Tender, Procedure.tender_id == Tender.id, isouter=True)
        .join(ParentRequest, Tender.parent_id == ParentRequest.id, isouter=True)
        .filter(_not_cancelled())
    )

    if hide_paid:
        q = q.filter(UpdPayment.pay_status != "paid")

    if search:
        s = search.strip()
        if s:
            cf = s.casefold()
            q = q.filter(
                or_(
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.upd, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.request_label, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(ParentRequest.code, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.supplier, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.contract, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.zrds, "")), cf) > 0,
                )
            )

    if sort not in _SORT_KEYS:
        sort = "created_at"
    _order = lambda col: col.asc().nulls_last()
    if sort == "created_at":
        q = q.order_by(UpdPayment.created_at.desc(), UpdPayment.id.desc())
    elif sort == "upd":
        q = q.order_by(_order(UpdPayment.upd), UpdPayment.id.asc())
    elif sort == "request":
        q = q.order_by(_order(ParentRequest.code), UpdPayment.id.asc())
    elif sort == "supplier":
        q = q.order_by(_order(UpdPayment.supplier), UpdPayment.id.asc())
    elif sort == "contract":
        q = q.order_by(_order(UpdPayment.contract), UpdPayment.id.asc())
    elif sort == "zrds":
        q = q.order_by(_order(UpdPayment.zrds), UpdPayment.id.asc())
    elif sort == "status":
        q = q.order_by(_order(UpdPayment.pay_status), UpdPayment.id.asc())
    elif sort == "srok":
        q = q.order_by(_order(UpdPayment.srok), UpdPayment.id.asc())
    elif sort == "amount":
        q = q.order_by(_order(UpdPayment.amount), UpdPayment.id.asc())

    page_data = paginate(q, page=page, page_size=page_size)
    today = calc.today_moscow()
    items: list[PaymentListItem] = []
    for row in page_data["items"]:
        upd, parent_code, delivery_n = row
        if upd.origin == "manual":
            request_display = upd.request_label
        else:
            request_display = parent_code or upd.request_label
        items.append(
            PaymentListItem(
                id=upd.id,
                upd=upd.upd,
                origin=upd.origin,
                request_display=request_display,
                supplier=upd.supplier,
                contract=upd.contract,
                zrds=upd.zrds,
                delivery_n=delivery_n if upd.origin == "delivery" else None,
                pay_status=upd.pay_status,
                is_overdue=calc.is_upd_overdue(upd, today),
                srok=upd.srok,
                pay_date=upd.pay_date,
                amount=upd.amount,
                created_at=upd.created_at,
            )
        )
    return PaginatedPayments(items=items, total=page_data["total"])


def _detail(db: Session, upd: UpdPayment) -> PaymentDetail:
    positions = (
        db.query(UpdPosition)
        .filter(UpdPosition.upd_payment_id == upd.id)
        .order_by(UpdPosition.id.asc())
        .all()
    )
    delivery = None
    if upd.delivery_id is not None:
        d = db.get(Delivery, upd.delivery_id)
        if d is not None:
            parent_code = None
            proc = db.get(Procedure, d.procedure_id)
            if proc is not None:
                tender = db.get(Tender, proc.tender_id)
                if tender is not None:
                    parent = db.get(ParentRequest, tender.parent_id)
                    parent_code = parent.code if parent else None
            delivery = PaymentDeliveryOut(
                n=d.n, procedure_id=d.procedure_id, parent_code=parent_code
            )
    return PaymentDetail(
        id=upd.id,
        upd=upd.upd,
        origin=upd.origin,
        delivery_id=upd.delivery_id,
        request_label=upd.request_label,
        supplier=upd.supplier,
        contract=upd.contract,
        zrds=upd.zrds,
        srok=upd.srok,
        amount=upd.amount,
        pay_status=upd.pay_status,
        pay_date=upd.pay_date,
        created_at=upd.created_at,
        positions=[UpdPositionOut.model_validate(p) for p in positions],
        delivery=delivery,
        is_overdue=calc.is_upd_overdue(upd, calc.today_moscow()),
    )


@router.post("", response_model=PaymentDetail, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> PaymentDetail:
    amount = payload.amount
    if amount is None and payload.positions:
        amount = calc.procedure_sum(payload.positions) or None
    new = UpdPayment(
        upd=payload.upd,
        origin="manual",
        delivery_id=None,
        request_label=payload.request_label,
        supplier=payload.supplier,
        contract=None,
        zrds=payload.zrds,
        srok=payload.srok,
        amount=amount,
        pay_status="await",
    )
    db.add(new)
    db.flush()  # assign new.id
    if payload.positions:
        for i, p in enumerate(payload.positions, start=1):
            db.add(
                UpdPosition(
                    upd_payment_id=new.id,
                    n=p.n if p.n is not None else i,
                    name=p.name,
                    unit=p.unit,
                    qty=p.qty,
                    price=p.price,
                )
            )
    db.commit()
    db.refresh(new)
    write_audit(
        db, entity_kind="upd_payment", entity_id=new.id,
        user=current_user, action="payment_create",
    )
    return _detail(db, new)


@router.get("/{payment_id}", response_model=PaymentDetail)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaymentDetail:
    upd = db.get(UpdPayment, payment_id)
    if upd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return _detail(db, upd)
