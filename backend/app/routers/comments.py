"""/comments router (Phase 10 B2) — лента + добавление + удаление.

Auth = require_password_changed (все аутентифицированные; «единое окно»).
Автор = текущий пользователь (снимок ФИО/роли server-side). Удаление: автор
своего ИЛИ Админ. POST/DELETE пишут audit_log. Spec: docs/31 §7, docs/01 §2.7.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import Comment, ParentRequest, Procedure, Tender, User
from app.permissions import can
from app.schemas.comments import CommentCreate, CommentList, CommentOut

router = APIRouter(prefix="/comments", tags=["comments"])

_TARGET_MODELS = {"parent": ParentRequest, "tender": Tender, "procedure": Procedure}


def _role_snapshot(user: User) -> str:
    """Human role label mirror of FE roleLabel (dashView). Snapshot survives deactivation."""
    if user.global_role:  # Админ / Руководитель
        return user.global_role
    if user.account_type == "global":
        return "Куратор"
    base = user.department or "—"
    return f"{base} · куратор" if user.is_curator else base


def _target_exists(db: Session, target_kind: str, target_id: int) -> bool:
    model = _TARGET_MODELS[target_kind]
    return db.query(model.id).filter(model.id == target_id).first() is not None


@router.get("", response_model=CommentList)
def list_comments(
    target_kind: str = Query(...),
    target_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> CommentList:
    q = (
        db.query(Comment)
        .filter(Comment.target_kind == target_kind, Comment.target_id == target_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    )
    data = paginate(q, page=page, page_size=page_size)
    return CommentList(items=data["items"], total=data["total"])


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_password_changed),
) -> CommentOut:
    if not _target_exists(db, body.target_kind, body.target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target not found")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty text")
    row = Comment(
        target_kind=body.target_kind,
        target_id=body.target_id,
        author_id=user.id,
        author=user.full_name,
        role=_role_snapshot(user),
        text=text,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, body.target_kind, body.target_id, user, "Добавлен комментарий")
    return row


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    cid: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_password_changed),
) -> Response:
    row = db.query(Comment).filter(Comment.id == cid).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if row.author_id != user.id and not can(user, "admin", "view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    db.delete(row)
    db.commit()
    write_audit(db, row.target_kind, row.target_id, user, "Удалён комментарий")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
