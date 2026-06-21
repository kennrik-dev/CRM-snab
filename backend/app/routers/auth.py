"""/auth router: login, logout, me, change-password."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user, get_current_user_no_refresh
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OkResponse,
    UserOut,
)
from app.security import (
    SESSION_COOKIE,
    make_session,
    session_cookie_kwargs,
    validate_password,
    verify_password,
)

SESSION_COOKIE_NAME = SESSION_COOKIE  # local alias for clarity in router code

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = db.query(User).filter_by(email=payload.email).first()

    # Generic error on any failure path — no hint which field was wrong.
    if (
        user is None
        or user.is_active != 1
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="неверные учётные данные",
        )

    remember = bool(payload.remember_me)
    token = make_session(user.id, remember=remember)
    cookie_kwargs = session_cookie_kwargs(secure=False)
    if remember:
        from app.security import SESSION_MAX_AGE
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_MAX_AGE,
            **cookie_kwargs,
        )
    else:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            **cookie_kwargs,
        )

    return LoginResponse(
        ok=True,
        must_change_password=bool(user.must_change_password == 1),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout", response_model=OkResponse)
def logout(
    response: Response,
    current_user: User = Depends(get_current_user_no_refresh),
) -> OkResponse:
    # current_user is required so logout works even when must_change_password is set
    _ = current_user
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return OkResponse(ok=True)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=MeResponse)
def me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    # Allowed even when must_change_password=1 (so the client can detect the flag).
    # Phase 3 will fill the real permissions map; for now, placeholder.
    permissions = {"_placeholder": {"view": True, "edit": False}}
    return MeResponse(
        user=UserOut.model_validate(current_user),
        permissions=permissions,
        must_change_password=bool(current_user.must_change_password == 1),
    )


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------

@router.post("/change-password", response_model=OkResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    # Allowed even when must_change_password=1.
    if not verify_password(payload.current, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="неверный текущий пароль",
        )

    try:
        validate_password(payload.new)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    from app.security import hash_password
    current_user.password_hash = hash_password(payload.new)
    current_user.must_change_password = 0
    db.commit()
    return OkResponse(ok=True)
