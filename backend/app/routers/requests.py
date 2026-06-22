"""/requests router: parent_request CRUD + positions (mass insert supported).

Phase 4.1 — locked spec from `docs/31-api.md` §2 and `docs/02-statuses.md` §7.1.
Phase 4.2 — adds POST /requests/{id}/take-to-work (Закупки only).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import apply_archive_filter, paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import (
    ParentRequest,
    Procedure,
    ProcedurePosition,
    RequestedPosition,
    Tender,
    User,
)
from app.permissions import require_action
from app.schemas.requests import (
    PaginatedRequests,
    PositionOut,
    ProcedureOut,
    RequestCreate,
    RequestDuplicate,
    RequestListItem,
    RequestOut,
    RequestPatch,
    RequestPositionIn,
    RequestPositionPatch,
    TakeToWorkResponse,
    TenderOut,
)


router = APIRouter(prefix="/requests", tags=["requests"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_request_out(db: Session, parent: ParentRequest) -> RequestOut:
    """Build a RequestOut from a ParentRequest ORM instance, including
    positions (asc by id) and tenders (asc by id) + their procedures."""
    positions = (
        db.query(RequestedPosition)
        .filter(RequestedPosition.parent_id == parent.id)
        .order_by(RequestedPosition.id.asc())
        .all()
    )
    tenders = (
        db.query(Tender)
        .filter(Tender.parent_id == parent.id)
        .order_by(Tender.id.asc())
        .all()
    )
    tender_outs = []
    for t in tenders:
        # procedures relation is defined on Tender
        procs = sorted(t.procedures, key=lambda p: p.id)
        tender_outs.append(
            TenderOut(
                id=t.id,
                parent_id=t.parent_id,
                num=t.num,
                procedures=[ProcedureOut.model_validate(p) for p in procs],
            )
        )

    return RequestOut(
        id=parent.id,
        code=parent.code,
        title=parent.title,
        mtr=parent.mtr,
        srok=parent.srok,
        zagruzka=parent.zagruzka,
        sostavitel=parent.sostavitel,
        created_by=parent.created_by,
        dept=parent.dept,
        status=parent.status,
        created_at=parent.created_at,
        positions=[PositionOut.model_validate(p) for p in positions],
        tenders=tender_outs,
    )


def _require_awaiting(parent: ParentRequest) -> None:
    """409 if parent is not in awaiting status."""
    if parent.status != "awaiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request is not awaiting",
        )


# ---------------------------------------------------------------------------
# GET /requests — list «Ожидают закупки»
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedRequests)
def list_requests(
    include_archived: bool = Query(False, description="Include cancelled requests"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status (awaiting|cancelled)",
    ),
    search: Optional[str] = Query(
        None,
        description="Case-insensitive substring on code OR title",
    ),
    sort: str = Query(
        "created_at",
        description="Sort field (created_at|code|title)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaginatedRequests:
    # Base query: parent_request
    q = db.query(ParentRequest)

    # status filter (explicit ?status= overrides include_archived)
    if status_filter:
        if status_filter not in ("awaiting", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid status",
            )
        q = q.filter(ParentRequest.status == status_filter)
    else:
        q = apply_archive_filter(q, include_archived=include_archived)
        # Taken-to-work parents (awaiting WITH a tender) have left
        # «Ожидают закупки» for «В закупке» (Phase 5) — exclude them from
        # every non-cancelled view. A genuinely cancelled parent (shown via
        # the include_archived toggle) is kept regardless of tender. So
        # "Показать отменённые" reveals only cancelled requests, never
        # taken-to-work ones. Per docs/02-statuses.md §7.1.
        no_tender = ~db.query(Tender).filter(
            Tender.parent_id == ParentRequest.id
        ).exists()
        if include_archived:
            q = q.filter((ParentRequest.status == "cancelled") | no_tender)
        else:
            q = q.filter(no_tender)

    # search (Unicode-aware via py_casefold, registered in app.db)
    if search:
        q_stripped = search.strip()
        if q_stripped:
            q_cf = q_stripped.casefold()
            code_match = func.instr(func.py_casefold(ParentRequest.code), q_cf) > 0
            title_match = func.instr(func.py_casefold(ParentRequest.title), q_cf) > 0
            q = q.filter(code_match | title_match)

    # sort
    if sort == "code":
        q = q.order_by(ParentRequest.code.asc(), ParentRequest.id.asc())
    elif sort == "title":
        q = q.order_by(ParentRequest.title.asc(), ParentRequest.id.asc())
    else:
        # default: created_at desc
        q = q.order_by(ParentRequest.created_at.desc(), ParentRequest.id.desc())

    # paginate
    page_data = paginate(q, page=page, page_size=page_size)
    items: list[ParentRequest] = page_data["items"]
    total: int = page_data["total"]

    # position_count per item
    items_out: list[RequestListItem] = []
    for parent in items:
        count = (
            db.query(func.count(RequestedPosition.id))
            .filter(RequestedPosition.parent_id == parent.id)
            .scalar()
        )
        items_out.append(
            RequestListItem(
                id=parent.id,
                code=parent.code,
                title=parent.title,
                mtr=parent.mtr,
                srok=parent.srok,
                zagruzka=parent.zagruzka,
                sostavitel=parent.sostavitel,
                status=parent.status,
                created_at=parent.created_at,
                position_count=count,
            )
        )

    return PaginatedRequests(items=items_out, total=total)


# ---------------------------------------------------------------------------
# POST /requests — create
# ---------------------------------------------------------------------------

@router.post("", response_model=RequestOut, status_code=status.HTTP_200_OK)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> RequestOut:
    # unique code
    existing = (
        db.query(ParentRequest).filter_by(code=payload.code).first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code already exists",
        )

    parent = ParentRequest(
        code=payload.code,
        title=payload.title,
        mtr=payload.mtr,
        srok=payload.srok,
        zagruzka=date.today().isoformat(),
        sostavitel=current_user.full_name,
        created_by=current_user.id,
        dept=payload.dept,
        status="awaiting",
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    # positions
    for p in payload.positions:
        db.add(
            RequestedPosition(
                parent_id=parent.id,
                name=p.name,
                qty=p.qty,
                unit=p.unit,
                gost_tu=p.gost_tu,
                doc_code=p.doc_code,
                num=p.num,
            )
        )
    if payload.positions:
        db.commit()

    write_audit(
        db,
        entity_kind="parent",
        entity_id=parent.id,
        user=current_user,
        action="create",
    )
    return _build_request_out(db, parent)


# ---------------------------------------------------------------------------
# GET /requests/{id} — full detail
# ---------------------------------------------------------------------------

@router.get("/{request_id}", response_model=RequestOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> RequestOut:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    return _build_request_out(db, parent)


# ---------------------------------------------------------------------------
# PATCH /requests/{id} — partial update (awaiting only)
# ---------------------------------------------------------------------------

@router.patch("/{request_id}", response_model=RequestOut)
def patch_request(
    request_id: int,
    payload: RequestPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> RequestOut:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    _require_awaiting(parent)

    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        parent.title = data["title"]
    if "mtr" in data:
        parent.mtr = data["mtr"]
    if "srok" in data:
        parent.srok = data["srok"]
    if "dept" in data:
        parent.dept = data["dept"]

    db.commit()
    db.refresh(parent)
    write_audit(
        db,
        entity_kind="parent",
        entity_id=parent.id,
        user=current_user,
        action="update",
    )
    return _build_request_out(db, parent)


# ---------------------------------------------------------------------------
# POST /requests/{id}/cancel — awaiting → cancelled
# ---------------------------------------------------------------------------

@router.post("/{request_id}/cancel", response_model=RequestOut)
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> RequestOut:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    _require_awaiting(parent)

    parent.status = "cancelled"
    db.commit()
    db.refresh(parent)
    write_audit(
        db,
        entity_kind="parent",
        entity_id=parent.id,
        user=current_user,
        action="cancel",
    )
    return _build_request_out(db, parent)


# ---------------------------------------------------------------------------
# POST /requests/{id}/uncancel — cancelled → awaiting
# ---------------------------------------------------------------------------

@router.post("/{request_id}/uncancel", response_model=RequestOut)
def uncancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> RequestOut:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    if parent.status != "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request is not cancelled",
        )

    parent.status = "awaiting"
    db.commit()
    db.refresh(parent)
    write_audit(
        db,
        entity_kind="parent",
        entity_id=parent.id,
        user=current_user,
        action="uncancel",
    )
    return _build_request_out(db, parent)


# ---------------------------------------------------------------------------
# POST /requests/{id}/duplicate — copy with new code (awaiting only)
# ---------------------------------------------------------------------------

@router.post("/{request_id}/duplicate", response_model=RequestOut)
def duplicate_request(
    request_id: int,
    payload: RequestDuplicate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> RequestOut:
    source = db.get(ParentRequest, request_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )

    # we only duplicate active (awaiting) requests
    if source.status != "awaiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only awaiting requests can be duplicated",
        )

    # new code must not already exist
    if db.query(ParentRequest).filter_by(code=payload.code).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code already exists",
        )

    new_parent = ParentRequest(
        code=payload.code,
        title=source.title,
        mtr=source.mtr,
        srok=source.srok,
        zagruzka=date.today().isoformat(),
        sostavitel=current_user.full_name,
        created_by=current_user.id,
        dept=source.dept,
        status="awaiting",
    )
    db.add(new_parent)
    db.commit()
    db.refresh(new_parent)

    # copy positions
    src_positions = (
        db.query(RequestedPosition)
        .filter(RequestedPosition.parent_id == source.id)
        .order_by(RequestedPosition.id.asc())
        .all()
    )
    for p in src_positions:
        db.add(
            RequestedPosition(
                parent_id=new_parent.id,
                name=p.name,
                qty=p.qty,
                unit=p.unit,
                gost_tu=p.gost_tu,
                doc_code=p.doc_code,
                num=p.num,
            )
        )
    if src_positions:
        db.commit()

    write_audit(
        db,
        entity_kind="parent",
        entity_id=new_parent.id,
        user=current_user,
        action="duplicate",
    )
    return _build_request_out(db, new_parent)


# ---------------------------------------------------------------------------
# GET /requests/{id}/positions — list positions
# ---------------------------------------------------------------------------

@router.get("/{request_id}/positions", response_model=list[PositionOut])
def list_positions(
    request_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> list[PositionOut]:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    rows = (
        db.query(RequestedPosition)
        .filter(RequestedPosition.parent_id == request_id)
        .order_by(RequestedPosition.id.asc())
        .all()
    )
    return [PositionOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /requests/{id}/positions — MASS INSERT (awaiting only)
# ---------------------------------------------------------------------------

@router.post(
    "/{request_id}/positions",
    response_model=list[PositionOut],
    status_code=status.HTTP_200_OK,
)
def mass_insert_positions(
    request_id: int,
    positions: list[RequestPositionIn],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> list[PositionOut]:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    _require_awaiting(parent)

    inserted: list[RequestedPosition] = []
    for p in positions:
        row = RequestedPosition(
            parent_id=parent.id,
            name=p.name,
            qty=p.qty,
            unit=p.unit,
            gost_tu=p.gost_tu,
            doc_code=p.doc_code,
            num=p.num,
        )
        db.add(row)
        inserted.append(row)
    if inserted:
        db.commit()
        for row in inserted:
            db.refresh(row)

    if inserted:
        write_audit(
            db,
            entity_kind="parent",
            entity_id=parent.id,
            user=current_user,
            action="positions_add",
        )
    return [PositionOut.model_validate(r) for r in inserted]


# ---------------------------------------------------------------------------
# PATCH /requests/{id}/positions/{pos_id} — partial update (awaiting only)
# ---------------------------------------------------------------------------

@router.patch(
    "/{request_id}/positions/{pos_id}",
    response_model=PositionOut,
)
def patch_position(
    request_id: int,
    pos_id: int,
    payload: RequestPositionPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> PositionOut:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    _require_awaiting(parent)

    pos = db.get(RequestedPosition, pos_id)
    if pos is None or pos.parent_id != request_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="position not found",
        )

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        pos.name = data["name"]
    if "qty" in data and data["qty"] is not None:
        pos.qty = data["qty"]
    if "unit" in data:
        pos.unit = data["unit"]
    if "gost_tu" in data:
        pos.gost_tu = data["gost_tu"]
    if "doc_code" in data:
        pos.doc_code = data["doc_code"]
    if "num" in data:
        pos.num = data["num"]

    db.commit()
    db.refresh(pos)
    write_audit(
        db,
        entity_kind="position",
        entity_id=pos.id,
        user=current_user,
        action="position_update",
    )
    return PositionOut.model_validate(pos)


# ---------------------------------------------------------------------------
# DELETE /requests/{id}/positions/{pos_id} — delete (awaiting only)
# ---------------------------------------------------------------------------

@router.delete("/{request_id}/positions/{pos_id}")
def delete_position(
    request_id: int,
    pos_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("komplektaciya", "edit")),
) -> dict:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )
    _require_awaiting(parent)

    pos = db.get(RequestedPosition, pos_id)
    if pos is None or pos.parent_id != request_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="position not found",
        )

    db.delete(pos)
    db.commit()
    write_audit(
        db,
        entity_kind="position",
        entity_id=pos_id,
        user=current_user,
        action="position_delete",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /requests/{id}/take-to-work — «Взять в работу» (Закупки only)
# ---------------------------------------------------------------------------
#
# Phase 4.2 — locked spec from `docs/31-api.md` §2 (take-to-work block).
#
# Behavior:
#   - 404 if request not found
#   - 409 if request.status != 'awaiting'
#   - 409 if request already has procedures (cannot take twice)
#   - creates Tender(parent_id, num=NULL)
#   - creates Procedure(tender_id, block='zakupka',
#     status_zakup='Новая' (служебное значение, ставится системой — НЕ из
#     справочника, per docs/02-statuses.md §3), block_entered_at=now ISO UTC)
#   - copies all RequestedPosition rows into ProcedurePosition with source_id
#     pointing at the original requested_position row
#   - audit 'take_to_work' on the parent_request
#   - returns {tender_id, procedure_id}
#
# Side effect: the parent disappears from GET /requests (default view) because
# the list filters out parents that already have tenders.


@router.post(
    "/{request_id}/take-to-work",
    response_model=TakeToWorkResponse,
)
def take_to_work(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("zakupka", "edit")),
) -> TakeToWorkResponse:
    parent = db.get(ParentRequest, request_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="request not found",
        )

    if parent.status != "awaiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request is not awaiting",
        )

    # 409 if already has procedures (cannot take to work twice)
    has_tenders = (
        db.query(Tender)
        .filter(Tender.parent_id == parent.id)
        .first()
    )
    if has_tenders is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request already taken to work",
        )

    # Create the tender (num=NULL is allowed at this phase).
    tender = Tender(parent_id=parent.id, num=None)
    db.add(tender)
    db.commit()
    db.refresh(tender)

    # Create the procedure in block='zakupka' with the system-set initial status.
    # Per docs/02-statuses.md §3, 'Новая' is a service value set on block entry
    # — it is NOT a справочник entry and must NOT appear in the user dropdown.
    procedure = Procedure(
        tender_id=tender.id,
        block="zakupka",
        status_zakup="Новая",
        block_entered_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(procedure)
    db.commit()
    db.refresh(procedure)

    # Copy RequestedPosition rows into ProcedurePosition with source_id.
    src_positions = (
        db.query(RequestedPosition)
        .filter(RequestedPosition.parent_id == parent.id)
        .order_by(RequestedPosition.id.asc())
        .all()
    )
    for p in src_positions:
        db.add(
            ProcedurePosition(
                procedure_id=procedure.id,
                source_id=p.id,
                name=p.name,
                qty=p.qty,
                unit=p.unit,
                gost_tu=p.gost_tu,
                doc_code=p.doc_code,
            )
        )
    if src_positions:
        db.commit()

    # Audit on the parent_request.
    write_audit(
        db,
        entity_kind="parent_request",
        entity_id=parent.id,
        user=current_user,
        action="take_to_work",
    )

    return TakeToWorkResponse(
        tender_id=tender.id,
        procedure_id=procedure.id,
    )