"""/procurement + /procedures routers: read/patch procedures + statuses.

Phase 5.1 — locked spec from
`docs/superpowers/plans/2026-06-23-phase5-zakupka.md` §5.1.
Phase 5.2 — split + priced positions CRUD + to-support (§5.2).
"""
from __future__ import annotations

from datetime import datetime, timezone
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
    RequestedPosition,
    Tender,
    User,
)
from app.permissions import require_action
from app.schemas.procedures import (
    PaginatedProcedures,
    ProcedureDetail,
    ProcedureListItem,
    ProcedurePatch,
    ProcedurePositionIn,
    ProcedurePositionOut,
    ProcedurePositionPatch,
    SplitIn,
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


def _source_total_qty(db: Session, source_id: int) -> float:
    """Σ(qty) of all ProcedurePosition rows referencing a requested_position.

    Used by the split-move invariant (docs/01-domain-model.md §2.4):
    Σ распределённого ≤ запрошенного. Compared against the requested qty with
    float tolerance.
    """
    return (
        db.query(func.coalesce(func.sum(ProcedurePosition.qty), 0))
        .filter(ProcedurePosition.source_id == source_id)
        .scalar()
        or 0.0
    )


# Float tolerance for the Σ≤requested invariant check.
_QTY_TOLERANCE = 1e-9


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


# ===========================================================================
# Phase 5.2 — split + priced positions CRUD + to-support
# ===========================================================================


# ---------------------------------------------------------------------------
# POST /procedures/{id}/split — MOVE qty into a new sister procedure
# ---------------------------------------------------------------------------

@router.post("/procedures/{procedure_id}/split", response_model=ProcedureDetail)
def split_procedure(
    procedure_id: int,
    payload: SplitIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> ProcedureDetail:
    """Split is MOVE: reduce each source position's qty and create a sister
    procedure holding the transferred qty. Per-position binding check is
    ``0 < item.qty <= source_position.qty`` else 422 — this is what enforces
    Σ≤requested, since a healthy DB starts at the cap after take-to-work and
    each move preserves Σ.
    """
    S = db.get(Procedure, procedure_id)
    if S is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )

    # Sister proc uniqueness (non-null) → 409. NULL ok.
    if payload.proc is not None:
        existing = (
            db.query(Procedure).filter(Procedure.proc == payload.proc).first()
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="proc already exists",
            )

    # --- Validation pre-pass: load every source position, verify each belongs
    # to S, and check the CUMULATIVE draw per source position (multiple items
    # may reference the same position) does not exceed its available qty. All
    # checks run BEFORE any mutation, so a 422/404 leaves the DB untouched
    # (atomic). Per docs/01-domain-model.md §2.4 (Σ распределённого ≤
    # запрошенного); Pydantic Field(gt=0) already rejects qty ≤ 0.
    sources: dict[int, list] = {}  # source_position_id -> [ProcedurePosition, drawn]
    for item in payload.positions:
        slot = sources.get(item.source_position_id)
        if slot is None:
            sp = db.get(ProcedurePosition, item.source_position_id)
            if sp is None or sp.procedure_id != S.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="source position not found",
                )
            slot = [sp, 0.0]
            sources[item.source_position_id] = slot
        sp, drawn = slot
        new_drawn = drawn + item.qty
        if new_drawn > sp.qty + _QTY_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="split qty exceeds available",
            )
        slot[1] = new_drawn

    # --- Apply pass: create the sister in the SAME tender and transfer
    # positions (MOVE: reduce source, sister receives the transferred qty).
    # No validation raises are possible here (pre-pass passed), so this is one
    # atomic transaction — a single commit at the end persists everything or
    # nothing.
    sister = Procedure(
        tender_id=S.tender_id,
        block="zakupka",
        status_zakup="Новая",
        block_entered_at=datetime.now(timezone.utc).isoformat(),
        supplier=payload.supplier,
        proc=payload.proc,
        mtr=payload.mtr if payload.mtr is not None else S.mtr,
    )
    db.add(sister)
    db.flush()  # assign sister.id without committing

    for item in payload.positions:
        sp = db.get(ProcedurePosition, item.source_position_id)
        # Sister position inherits the source's catalog fields + source_id + price.
        db.add(
            ProcedurePosition(
                procedure_id=sister.id,
                source_id=sp.source_id,
                name=sp.name,
                qty=item.qty,
                unit=sp.unit,
                gost_tu=sp.gost_tu,
                doc_code=sp.doc_code,
                price=sp.price,
            )
        )
        # Reduce the source position; fully-transferred → delete.
        remaining = sp.qty - item.qty
        if abs(remaining) < _QTY_TOLERANCE:
            db.delete(sp)
        else:
            sp.qty = remaining

    db.commit()  # atomic: sister + all transfers persist together
    db.refresh(sister)

    write_audit(
        db,
        entity_kind="procedure",
        entity_id=S.id,
        user=current_user,
        action="split",
    )
    return _build_detail(db, sister)


# ---------------------------------------------------------------------------
# GET /procedures/{id}/positions — list (asc by id)
# ---------------------------------------------------------------------------

@router.get(
    "/procedures/{procedure_id}/positions",
    response_model=list[ProcedurePositionOut],
)
def list_procedure_positions(
    procedure_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> list[ProcedurePositionOut]:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )
    rows = (
        db.query(ProcedurePosition)
        .filter(ProcedurePosition.procedure_id == procedure_id)
        .order_by(ProcedurePosition.id.asc())
        .all()
    )
    return [ProcedurePositionOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /procedures/{id}/positions — mass insert
# ---------------------------------------------------------------------------

@router.post(
    "/procedures/{procedure_id}/positions",
    response_model=list[ProcedurePositionOut],
    status_code=status.HTTP_200_OK,
)
def add_procedure_positions(
    procedure_id: int,
    positions: list[ProcedurePositionIn],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> list[ProcedurePositionOut]:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )

    inserted: list[ProcedurePosition] = []
    for p in positions:
        # Sourced positions are capped by the requested qty (Σ≤requested).
        if p.source_id is not None:
            requested = db.get(RequestedPosition, p.source_id)
            new_total = _source_total_qty(db, p.source_id) + p.qty
            if requested is None or new_total > requested.qty + _QTY_TOLERANCE:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="qty exceeds requested",
                )
        row = ProcedurePosition(
            procedure_id=proc.id,
            source_id=p.source_id,
            name=p.name,
            qty=p.qty,
            unit=p.unit,
            gost_tu=p.gost_tu,
            doc_code=p.doc_code,
            price=p.price,
        )
        db.add(row)
        inserted.append(row)

    if inserted:
        db.commit()
        for row in inserted:
            db.refresh(row)
        write_audit(
            db,
            entity_kind="procedure",
            entity_id=proc.id,
            user=current_user,
            action="positions_add",
        )
    return [ProcedurePositionOut.model_validate(r) for r in inserted]


# ---------------------------------------------------------------------------
# PATCH /procedures/{id}/positions/{pos_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/procedures/{procedure_id}/positions/{pos_id}",
    response_model=ProcedurePositionOut,
)
def patch_procedure_position(
    procedure_id: int,
    pos_id: int,
    payload: ProcedurePositionPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> ProcedurePositionOut:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )

    pos = db.get(ProcedurePosition, pos_id)
    if pos is None or pos.procedure_id != procedure_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="position not found",
        )

    data = payload.model_dump(exclude_unset=True)

    # Sourced qty change re-checks the global Σ≤requested invariant.
    if "qty" in data and data["qty"] is not None and pos.source_id is not None:
        requested = db.get(RequestedPosition, pos.source_id)
        new_total = (
            _source_total_qty(db, pos.source_id) - pos.qty + data["qty"]
        )
        if requested is None or new_total > requested.qty + _QTY_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="qty exceeds requested",
            )

    for field in ("name", "qty", "unit", "gost_tu", "doc_code", "price"):
        if field in data:
            setattr(pos, field, data[field])

    db.commit()
    db.refresh(pos)
    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="position_update",
    )
    return ProcedurePositionOut.model_validate(pos)


# ---------------------------------------------------------------------------
# DELETE /procedures/{id}/positions/{pos_id}
# ---------------------------------------------------------------------------

@router.delete("/procedures/{procedure_id}/positions/{pos_id}")
def delete_procedure_position(
    procedure_id: int,
    pos_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> dict:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )

    pos = db.get(ProcedurePosition, pos_id)
    if pos is None or pos.procedure_id != procedure_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="position not found",
        )

    db.delete(pos)
    db.commit()
    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="position_delete",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /procedures/{id}/to-support — hand off to Сопровождение
# ---------------------------------------------------------------------------

@router.post("/procedures/{procedure_id}/to-support", response_model=ProcedureDetail)
def to_support(
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
    # Only «На сделку» may advance to Сопровождение (covers Новая/Отменена/other).
    if proc.status_zakup != "На сделку":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="procedure is not ready for support",
        )

    proc.block = "soprovozhdenie"
    proc.status_postavki = "Новая"
    proc.block_entered_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(proc)

    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="to_support",
    )
    return _build_detail(db, proc)
