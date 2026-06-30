"""/history router (Phase 10 B3) — «История» в карточках (audit_log, read-only).

Auth = require_password_changed. entity_kind не вайтлистится (свободный TEXT).
Актёр = User.full_name через batch-lookup; null user_id → «Система».
Spec: docs/31 §7, docs/33 §2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit import paginate
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import AuditLog, User
from app.schemas.history import AuditEntryOut, HistoryList

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryList)
def list_history(
    entity_kind: str = Query(...),
    entity_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> HistoryList:
    q = (
        db.query(AuditLog)
        .filter(AuditLog.entity_kind == entity_kind, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    data = paginate(q, page=page, page_size=page_size)
    items = data["items"]
    uids = {row.user_id for row in items if row.user_id is not None}
    names = {}
    if uids:
        names = {
            u.id: u.full_name
            for u in db.query(User.id, User.full_name).filter(User.id.in_(uids)).all()
        }
    out = [
        AuditEntryOut(
            id=row.id,
            action=row.action,
            actor=names.get(row.user_id, "Система"),
            created_at=row.created_at,
        )
        for row in items
    ]
    return HistoryList(items=out, total=data["total"])
