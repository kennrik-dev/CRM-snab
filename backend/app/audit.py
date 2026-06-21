"""Audit + pagination helpers for Phase 3 routers."""
from __future__ import annotations

from typing import Union

from sqlalchemy.orm import Query

from app.models import AuditLog, ParentRequest, User


# ---------------------------------------------------------------------------
# write_audit
# ---------------------------------------------------------------------------

def write_audit(
    db,
    entity_kind: str,
    entity_id: int,
    user: Union[User, int, None],
    action: str,
) -> AuditLog:
    """Append one audit_log row + commit.

    `user` may be a User instance or a user-id int (or None).
    Returns the persisted AuditLog (refreshed).
    """
    if isinstance(user, User):
        user_id = user.id
    else:
        user_id = user  # int or None — both legal

    row = AuditLog(
        entity_kind=entity_kind,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# paginate
# ---------------------------------------------------------------------------

def paginate(query: Query, page: int, page_size: int = 50) -> dict:
    """Return {"items": [...], "total": int}. page is 1-based."""
    total = query.order_by(None).count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# apply_archive_filter
# ---------------------------------------------------------------------------

def apply_archive_filter(query: Query, include_archived: bool = False) -> Query:
    """Filter parent_request query to status='awaiting' unless include_archived=True."""
    if not include_archived:
        return query.filter(ParentRequest.status == "awaiting")
    return query


__all__ = [
    "write_audit",
    "paginate",
    "apply_archive_filter",
]
