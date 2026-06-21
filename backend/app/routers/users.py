"""/users router: admin-only CRUD + reset-password."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import (
    get_current_user,
    require_password_changed,
)
from app.models import User
from app.schemas.users import (
    ALLOWED_DEPARTMENTS,
    ALLOWED_GLOBAL_ROLES,
    PaginatedUsersResponse,
    ResetPasswordRequest,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
)
from app.security import hash_password, validate_password

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Admin guard
# ---------------------------------------------------------------------------

def _require_admin(current_user: User) -> User:
    """Caller must already be authenticated and have password already changed."""
    if current_user.global_role != "Админ":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin only",
        )
    return current_user


# ---------------------------------------------------------------------------
# GET /users — paginated list
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedUsersResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
) -> PaginatedUsersResponse:
    _require_admin(current_user)

    total = db.query(User).count()
    rows = (
        db.query(User)
        .order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedUsersResponse(
        items=[UserOut.model_validate(r) for r in rows],
        total=total,
    )


# ---------------------------------------------------------------------------
# POST /users — create
# ---------------------------------------------------------------------------

@router.post("", response_model=UserOut, status_code=status.HTTP_200_OK)
def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
) -> UserOut:
    _require_admin(current_user)

    # account_type-specific field validation
    if payload.account_type == "department":
        if payload.department not in ALLOWED_DEPARTMENTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid department",
            )
    elif payload.account_type == "global":
        if payload.global_role not in ALLOWED_GLOBAL_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid global_role",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid account_type",
        )

    # password complexity
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # unique email
    if db.query(User).filter_by(email=payload.email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        account_type=payload.account_type,
        department=payload.department if payload.account_type == "department" else None,
        is_curator=1 if payload.is_curator else 0,
        global_role=payload.global_role if payload.account_type == "global" else None,
        is_active=1,
        must_change_password=1,
        created_by=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# PATCH /users/{id} — partial update
# ---------------------------------------------------------------------------

@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
) -> UserOut:
    _require_admin(current_user)

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    data = payload.model_dump(exclude_unset=True)

    # Prevent self-deactivation
    if "is_active" in data and data["is_active"] is False and user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cannot deactivate yourself",
        )

    if "full_name" in data and data["full_name"] is not None:
        user.full_name = data["full_name"]

    if "department" in data:
        new_dept = data["department"]
        if new_dept is not None and new_dept not in ALLOWED_DEPARTMENTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid department",
            )
        user.department = new_dept

    if "is_curator" in data and data["is_curator"] is not None:
        user.is_curator = 1 if data["is_curator"] else 0

    if "global_role" in data:
        new_role = data["global_role"]
        if new_role is not None and new_role not in ALLOWED_GLOBAL_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid global_role",
            )
        user.global_role = new_role

    if "is_active" in data and data["is_active"] is not None:
        user.is_active = 1 if data["is_active"] else 0

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# POST /users/{id}/reset-password
# ---------------------------------------------------------------------------

@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_password_changed),
    db: Session = Depends(get_db),
) -> dict:
    _require_admin(current_user)

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    try:
        validate_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = 1
    db.commit()
    return {"ok": True}
