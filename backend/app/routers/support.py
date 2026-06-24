"""/support + /deliveries routers (Phase 6.2).

GET /support           — list procedures in block='soprovozhdenie' (active default).
PATCH /procedures/{id} — Б2 fields (lives in procurement.py; block-scoped).
POST   /procedures/{id}/deliveries — create partial delivery (≥1 positions).
DELETE /deliveries/{id}            — disband (transit only).
PATCH  /deliveries/{id}            — transit→done, doc flags, date/eta.
POST   /deliveries/{id}/upd        — upsert upd_payment (origin=delivery, await).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app import calculations as calc
from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import (
    Delivery,
    Dict,
    ParentRequest,
    Procedure,
    ProcedurePosition,
    Tender,
    UpdPayment,
    User,
)
from app.permissions import require_action
from app.schemas.deliveries import (
    DeliveryCreate,
    DeliveryOut,
    DeliveryPatch,
    DeliveryUpdOut,
    PaginatedSupport,
    SupportListItem,
    UpdIn,
)


router = APIRouter(tags=["support"])

_SORT_KEYS = {
    "created_at", "code", "proc", "supplier", "contract_sum",
    "status_postavki", "status_sdelki", "srok_dd", "plan_date", "fakt_date",
}


def _await_upd_exists():
    return exists(
        select(UpdPayment.id)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id)
        .where(Delivery.procedure_id == Procedure.id)
        .where(UpdPayment.pay_status == "await")
    )


def _any_upd_exists():
    return exists(
        select(UpdPayment.id)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id)
        .where(Delivery.procedure_id == Procedure.id)
    )


@router.get("/support", response_model=PaginatedSupport)
def list_support(
    include_archived: bool = Query(False, description="Include cancelled + completed"),
    search: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaginatedSupport:
    q = (
        db.query(Procedure)
        .join(Tender, Procedure.tender_id == Tender.id)
        .join(ParentRequest, Tender.parent_id == ParentRequest.id)
        .filter(Procedure.block == "soprovozhdenie")
    )

    # Решение 6: archived = Отменена OR completed(Поставлено + ≥1 upd + all paid).
    completed = and_(
        Procedure.status_postavki == "Поставлено",
        _any_upd_exists(),
        ~_await_upd_exists(),
    )
    archived = or_(Procedure.status_postavki == "Отменена", completed)
    if not include_archived:
        q = q.filter(~archived)

    if search:
        s = search.strip()
        if s:
            cf = s.casefold()
            q = q.filter(
                or_(
                    func.instr(func.py_casefold(ParentRequest.code), cf) > 0,
                    func.instr(func.py_casefold(ParentRequest.title), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Procedure.proc, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Tender.num, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Procedure.supplier, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Procedure.contract, "")), cf) > 0,
                )
            )

    if sort not in _SORT_KEYS:
        sort = "created_at"
    _order = lambda col: col.asc().nulls_last()
    if sort == "created_at":
        q = q.order_by(Procedure.created_at.desc(), Procedure.id.desc())
    elif sort == "code":
        q = q.order_by(ParentRequest.code.asc(), Procedure.id.asc())
    elif sort == "proc":
        q = q.order_by(_order(Procedure.proc), Procedure.id.asc())
    elif sort == "supplier":
        q = q.order_by(_order(Procedure.supplier), Procedure.id.asc())
    elif sort == "contract_sum":
        q = q.order_by(_order(Procedure.contract_sum), Procedure.id.asc())
    elif sort == "status_postavki":
        q = q.order_by(_order(Procedure.status_postavki), Procedure.id.asc())
    elif sort == "status_sdelki":
        q = q.order_by(_order(Procedure.status_sdelki), Procedure.id.asc())
    elif sort in ("srok_dd", "plan_date", "fakt_date"):
        q = q.order_by(_order(getattr(Procedure, sort)), Procedure.id.asc())

    page_data = paginate(q, page=page, page_size=page_size)
    items: list[Procedure] = page_data["items"]
    total: int = page_data["total"]

    today = calc.today_moscow()
    items_out: list[SupportListItem] = []
    for proc in items:
        positions = (
            db.query(ProcedurePosition)
            .filter(ProcedurePosition.procedure_id == proc.id)
            .all()
        )
        deliveries = (
            db.query(Delivery).filter(Delivery.procedure_id == proc.id).all()
        )
        delivered, total_pos, _ = calc.progress(positions, deliveries)
        tender = proc.tender
        parent = tender.parent if tender else None
        items_out.append(
            SupportListItem(
                id=proc.id,
                proc=proc.proc,
                tender_num=tender.num if tender else None,
                code=parent.code if parent else "",
                title=parent.title if parent else "",
                mtr=proc.mtr if proc.mtr is not None else (parent.mtr if parent else None),
                supplier=proc.supplier,
                contract=proc.contract,
                contract_sum=proc.contract_sum,
                status_sdelki=proc.status_sdelki,
                status_postavki=proc.status_postavki,
                srok_dd=proc.srok_dd,
                plan_date=proc.plan_date,
                fakt_date=proc.fakt_date,
                is_overdue=calc.is_procedure_overdue(proc.srok_dd, proc.status_postavki, today),
                overdue_pct=calc.overdue_pct(positions, deliveries, proc.srok_dd, today),
                docs=calc.docs_aggregate(deliveries),
                progress_delivered=delivered,
                progress_total=total_pos,
                created_at=proc.created_at,
            )
        )

    return PaginatedSupport(items=items_out, total=total)


def _delivery_out(db: Session, d: Delivery) -> DeliveryOut:
    upd = db.query(UpdPayment).filter(UpdPayment.delivery_id == d.id).first()
    return DeliveryOut(
        id=d.id, n=d.n, status=d.status, date=d.date, eta=d.eta,
        doc_ttn=d.doc_ttn or 0, doc_m15=d.doc_m15 or 0,
        doc_upd=d.doc_upd or 0, doc_sert=d.doc_sert or 0,
        upd=DeliveryUpdOut(upd=upd.upd, pay_status=upd.pay_status) if upd else None,
    )


@router.post(
    "/procedures/{procedure_id}/deliveries",
    response_model=DeliveryOut,
    status_code=status.HTTP_200_OK,
)
def create_delivery(
    procedure_id: int,
    payload: DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> DeliveryOut:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="procedure not found")
    if proc.block != "soprovozhdenie":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="procedure is not in support block")

    # Validate every position: exists, belongs to proc, still awaiting (delivery_id NULL).
    seen: set[int] = set()
    for pid in payload.positions:
        pos = db.get(ProcedurePosition, pid)
        if pos is None or pos.procedure_id != proc.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
        if pos.delivery_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="position already in a delivery")
        if pid in seen:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="duplicate position in delivery")
        seen.add(pid)

    next_n = (db.query(func.max(Delivery.n))
              .filter(Delivery.procedure_id == proc.id).scalar() or 0) + 1
    d = Delivery(procedure_id=proc.id, n=next_n, status="transit")
    db.add(d)
    db.flush()  # assign d.id
    for pid in payload.positions:
        db.get(ProcedurePosition, pid).delivery_id = d.id

    db.commit()
    db.refresh(d)
    write_audit(db, entity_kind="procedure", entity_id=proc.id,
                user=current_user, action="delivery_create")
    return _delivery_out(db, d)


@router.delete("/deliveries/{delivery_id}")
def delete_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> dict:
    d = db.get(Delivery, delivery_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery not found")
    if d.status != "transit":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="only transit deliveries can be disbanded")
    # FK guard: an issued UPD references this delivery → forbid.
    if db.query(UpdPayment).filter(UpdPayment.delivery_id == d.id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="cannot disband delivery with issued UPD")
    # Return positions to awaiting, then drop the delivery.
    (db.query(ProcedurePosition)
        .filter(ProcedurePosition.delivery_id == d.id)
        .update({ProcedurePosition.delivery_id: None}))
    proc_id = d.procedure_id
    db.delete(d)
    db.commit()
    write_audit(db, entity_kind="procedure", entity_id=proc_id,
                user=current_user, action="delivery_delete")
    return {"ok": True}
