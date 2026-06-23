"""/procurement + /procedures routers: read/patch procedures + statuses.

Phase 5.1 — locked spec from
`docs/superpowers/plans/2026-06-23-phase5-zakupka.md` §5.1.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import (
    Dict,
    ParentRequest,
    Procedure,
    ProcedurePosition,
    Tender,
    User,
)
from app.permissions import require_action
from app.schemas.procedures import (
    PaginatedProcedures,
    ProcedureDetail,
    ProcedureListItem,
    ProcedurePatch,
    ProcedurePositionOut,
)


router = APIRouter(tags=["procurement"])


# ---------------------------------------------------------------------------
# Sort whitelist (anything else → default created_at desc, no 500)
# ---------------------------------------------------------------------------

_SORT_KEYS = {
    "created_at",
    "code",
    "num",
    "proc",
    "supplier",
    "status",
    "mtr",
    "zagruzka",
    "pub_start",
    "pub_end",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_detail(db: Session, proc: Procedure) -> ProcedureDetail:
    """Build a ProcedureDetail from a Procedure ORM instance (with positions
    ascending by id) — fetching the tender + parent for header fields."""
    tender = db.get(Tender, proc.tender_id)
    parent = db.get(ParentRequest, tender.parent_id) if tender else None

    positions = (
        db.query(ProcedurePosition)
        .filter(ProcedurePosition.procedure_id == proc.id)
        .order_by(ProcedurePosition.id.asc())
        .all()
    )

    return ProcedureDetail(
        id=proc.id,
        proc=proc.proc,
        tender_id=proc.tender_id,
        tender_num=tender.num if tender else None,
        parent_id=tender.parent_id if tender else 0,
        code=parent.code if parent else "",
        title=parent.title if parent else "",
        mtr=proc.mtr if proc.mtr is not None else (parent.mtr if parent else None),
        supplier=proc.supplier,
        fio_zakupshchik=proc.fio_zakupshchik,
        pub_start=proc.pub_start,
        pub_end=proc.pub_end,
        zagruzka=parent.zagruzka if parent else "",
        block=proc.block,
        status_zakup=proc.status_zakup,
        created_at=proc.created_at,
        positions=[ProcedurePositionOut.model_validate(p) for p in positions],
    )


# ---------------------------------------------------------------------------
# GET /procurement — list procedures in block='zakupka'
# ---------------------------------------------------------------------------

@router.get("/procurement", response_model=PaginatedProcedures)
def list_procurement(
    include_archived: bool = Query(
        False, description="Include procedures with status_zakup='Отменена'"
    ),
    search: Optional[str] = Query(
        None, description="Case-insensitive substring on proc/tender.num/supplier/code/title",
    ),
    sort: str = Query(
        "created_at",
        description="Sort field (created_at|code|num|proc|supplier|status|mtr|zagruzka|pub_start|pub_end)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaginatedProcedures:
    q = (
        db.query(Procedure)
        .join(Tender, Procedure.tender_id == Tender.id)
        .join(ParentRequest, Tender.parent_id == ParentRequest.id)
        .filter(Procedure.block == "zakupka")
    )

    # status_zakup filter: active excludes only 'Отменена' (but INCLUDES NULL).
    if not include_archived:
        q = q.filter(
            or_(
                Procedure.status_zakup.is_(None),
                Procedure.status_zakup != "Отменена",
            )
        )

    # search (Unicode-aware via py_casefold + instr)
    if search:
        s = search.strip()
        if s:
            cf = s.casefold()
            code_match = func.instr(func.py_casefold(ParentRequest.code), cf) > 0
            title_match = func.instr(func.py_casefold(ParentRequest.title), cf) > 0
            proc_match = func.instr(func.py_casefold(func.coalesce(Procedure.proc, "")), cf) > 0
            tender_match = func.instr(func.py_casefold(func.coalesce(Tender.num, "")), cf) > 0
            supplier_match = func.instr(
                func.py_casefold(func.coalesce(Procedure.supplier, "")), cf
            ) > 0
            q = q.filter(proc_match | tender_match | supplier_match | code_match | title_match)

    # sort (whitelist; invalid → default created_at desc)
    if sort not in _SORT_KEYS:
        sort = "created_at"
    if sort == "created_at":
        q = q.order_by(Procedure.created_at.desc(), Procedure.id.desc())
    elif sort == "code":
        q = q.order_by(ParentRequest.code.asc(), Procedure.id.asc())
    elif sort == "num":
        q = q.order_by(Tender.num.asc().nulls_last(), Procedure.id.asc())
    elif sort == "proc":
        q = q.order_by(Procedure.proc.asc().nulls_last(), Procedure.id.asc())
    elif sort == "supplier":
        q = q.order_by(Procedure.supplier.asc().nulls_last(), Procedure.id.asc())
    elif sort == "status":
        q = q.order_by(Procedure.status_zakup.asc().nulls_last(), Procedure.id.asc())
    elif sort == "mtr":
        q = q.order_by(Procedure.mtr.asc().nulls_last(), Procedure.id.asc())
    elif sort == "zagruzka":
        q = q.order_by(ParentRequest.zagruzka.asc(), Procedure.id.asc())
    elif sort == "pub_start":
        q = q.order_by(Procedure.pub_start.asc().nulls_last(), Procedure.id.asc())
    elif sort == "pub_end":
        q = q.order_by(Procedure.pub_end.asc().nulls_last(), Procedure.id.asc())

    page_data = paginate(q, page=page, page_size=page_size)
    items: list[Procedure] = page_data["items"]
    total: int = page_data["total"]

    # Build list items (correlated scalar count per row — no join inflation).
    items_out: list[ProcedureListItem] = []
    for proc in items:
        position_count = (
            db.query(func.count(ProcedurePosition.id))
            .filter(ProcedurePosition.procedure_id == proc.id)
            .scalar()
        ) or 0
        # tender.num + parent.code/title/zagruzka/mtr — load via relationship
        tender = proc.tender
        parent = tender.parent if tender else None
        mtr = proc.mtr if proc.mtr is not None else (parent.mtr if parent else None)
        items_out.append(
            ProcedureListItem(
                id=proc.id,
                proc=proc.proc,
                tender_num=tender.num if tender else None,
                code=parent.code if parent else "",
                title=parent.title if parent else "",
                mtr=mtr,
                supplier=proc.supplier,
                fio_zakupshchik=proc.fio_zakupshchik,
                pub_start=proc.pub_start,
                pub_end=proc.pub_end,
                zagruzka=parent.zagruzka if parent else "",
                position_count=position_count,
                status_zakup=proc.status_zakup,
                created_at=proc.created_at,
            )
        )

    return PaginatedProcedures(items=items_out, total=total)


# ---------------------------------------------------------------------------
# GET /procedures/{id} — detail
# ---------------------------------------------------------------------------

@router.get("/procedures/{procedure_id}", response_model=ProcedureDetail)
def get_procedure(
    procedure_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> ProcedureDetail:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )
    return _build_detail(db, proc)


# ---------------------------------------------------------------------------
# PATCH /procedures/{id} — partial update
# ---------------------------------------------------------------------------

@router.patch("/procedures/{procedure_id}", response_model=ProcedureDetail)
def patch_procedure(
    procedure_id: int,
    payload: ProcedurePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> ProcedureDetail:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )

    data = payload.model_dump(exclude_unset=True)

    # status_zakup validation against the dict (6 values). Service-only
    # values ('Новая', 'Отменена') are NOT in the dict → 422.
    if "status_zakup" in data and data["status_zakup"] is not None:
        allowed = {
            row.value
            for row in db.query(Dict).filter(Dict.kind == "status_zakup").all()
        }
        if data["status_zakup"] not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid status_zakup",
            )

    # Unique proc (non-null) duplicate → 409. Multiple NULLs allowed.
    if "proc" in data and data["proc"] is not None and data["proc"] != proc.proc:
        existing = (
            db.query(Procedure).filter(Procedure.proc == data["proc"]).first()
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="proc already exists",
            )

    # tender_num → proc.tender.num. Unique (non-null) duplicate → 409.
    tender = db.get(Tender, proc.tender_id)
    if "tender_num" in data and data["tender_num"] is not None and data["tender_num"] != (tender.num if tender else None):
        existing_tender = (
            db.query(Tender).filter(Tender.num == data["tender_num"]).first()
        )
        if existing_tender is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="tender num already exists",
            )

    # Apply scalar fields to the procedure.
    for field in ("proc", "supplier", "fio_zakupshchik", "mtr", "pub_start", "pub_end", "status_zakup"):
        if field in data:
            setattr(proc, field, data[field])

    # Apply tender_num to the tender row.
    if "tender_num" in data and tender is not None:
        tender.num = data["tender_num"]

    db.commit()
    db.refresh(proc)
    if tender is not None:
        db.refresh(tender)

    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="update",
    )
    return _build_detail(db, proc)


# ---------------------------------------------------------------------------
# POST /procedures/{id}/cancel — → status_zakup='Отменена'
# ---------------------------------------------------------------------------

@router.post("/procedures/{procedure_id}/cancel", response_model=ProcedureDetail)
def cancel_procedure(
    procedure_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> ProcedureDetail:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )
    if proc.status_zakup == "Отменена":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="procedure already cancelled",
        )

    proc.status_zakup = "Отменена"
    db.commit()
    db.refresh(proc)

    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="cancel",
    )
    return _build_detail(db, proc)


# ---------------------------------------------------------------------------
# POST /procedures/{id}/uncancel — → status_zakup='Новая'
# ---------------------------------------------------------------------------

@router.post("/procedures/{procedure_id}/uncancel", response_model=ProcedureDetail)
def uncancel_procedure(
    procedure_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> ProcedureDetail:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )
    if proc.status_zakup != "Отменена":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="procedure is not cancelled",
        )

    proc.status_zakup = "Новая"
    db.commit()
    db.refresh(proc)

    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="uncancel",
    )
    return _build_detail(db, proc)
