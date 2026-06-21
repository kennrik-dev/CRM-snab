"""/dict router: status_zakup / status_sdelki lookup + admin-only mutations.

Phase 3.3 — locked spec.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import Dict, User
from app.permissions import require_action

router = APIRouter(prefix="/dict", tags=["dict"])


# ---------------------------------------------------------------------------
# Allowed kinds (mirror DB CHECK constraint on dict.kind)
# ---------------------------------------------------------------------------
ALLOWED_KINDS = ("status_zakup", "status_sdelki")


# ---------------------------------------------------------------------------
# Schemas (inlined per task spec)
# ---------------------------------------------------------------------------

class DictCreateRequest(BaseModel):
    value: str = Field(min_length=1)
    sort_order: Optional[int] = None


class DictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    value: str
    sort_order: Optional[int] = None


# ---------------------------------------------------------------------------
# Kind validator (path-param)
# ---------------------------------------------------------------------------

def _validate_kind(kind: str = Path(...)) -> str:
    if kind not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unknown kind",
        )
    return kind


# ---------------------------------------------------------------------------
# GET /dict/{kind} — list
# ---------------------------------------------------------------------------

@router.get("/{kind}", response_model=list[DictOut])
def list_dict(
    kind: str = Depends(_validate_kind),
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
) -> list[DictOut]:
    """List dict rows for `kind`, ordered by (sort_order ASC NULLS LAST, value ASC)."""
    rows = (
        db.query(Dict)
        .filter(Dict.kind == kind)
        .order_by(Dict.sort_order.asc().nulls_last(), Dict.value.asc())
        .all()
    )
    return [DictOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /dict/{kind} — admin-only create
# ---------------------------------------------------------------------------

@router.post(
    "/{kind}",
    response_model=DictOut,
    status_code=status.HTTP_200_OK,
)
def create_dict(
    payload: DictCreateRequest,
    kind: str = Depends(_validate_kind),
    current_user: User = Depends(require_action("admin", "edit")),
    db: Session = Depends(get_db),
) -> DictOut:
    existing = (
        db.query(Dict).filter_by(kind=kind, value=payload.value).first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="value already exists for this kind",
        )

    row = Dict(
        kind=kind,
        value=payload.value,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, entity_kind="dict", entity_id=row.id, user=current_user, action="create")
    return DictOut.model_validate(row)


# ---------------------------------------------------------------------------
# DELETE /dict/{kind}/{dict_id} — admin-only delete
# ---------------------------------------------------------------------------

@router.delete("/{kind}/{dict_id}")
def delete_dict(
    kind: str = Depends(_validate_kind),
    dict_id: int = Path(..., ge=1),
    current_user: User = Depends(require_action("admin", "edit")),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Dict, dict_id)
    if row is None or row.kind != kind:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dict row not found",
        )

    db.delete(row)
    db.commit()
    write_audit(db, entity_kind="dict", entity_id=dict_id, user=current_user, action="delete")
    return {"ok": True}
