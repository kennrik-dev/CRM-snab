"""Shared FastAPI dependencies (auth + DB helpers)."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import (
    SESSION_COOKIE,
    make_session,
    read_session,
    session_cookie_kwargs,
)


# Re-exported constant (single source of truth in app.security).
SESSION_COOKIE_NAME = SESSION_COOKIE


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------

def _load_user_from_cookie(
    request: Request,
    response: Response,
    db: Session,
) -> Optional[User]:
    """Resolve a User from the session cookie, refreshing last_active.

    Returns None if the cookie is missing/invalid or the user is inactive.
    On successful auth, rotates the cookie with an updated last_active
    timestamp so the idle-timeout window restarts.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    payload = read_session(token)
    if payload is None:
        return None

    user_id = payload.get("user_id")
    remember = bool(payload.get("remember"))
    if not isinstance(user_id, int):
        return None

    user = db.get(User, user_id)
    if user is None or user.is_active != 1:
        return None

    # Rotate cookie: refresh last_active to "now" by re-signing.
    new_token = make_session(user.id, remember=remember)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=new_token,
        max_age=None if not remember else None,  # session cookie if not remember
        **session_cookie_kwargs(secure=False),
    )
    # When remember=True, also set max_age explicitly.
    if remember:
        from app.security import SESSION_MAX_AGE
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=new_token,
            max_age=SESSION_MAX_AGE,
            **session_cookie_kwargs(secure=False),
        )

    return user


def get_current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    user = _load_user_from_cookie(request, response, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    return user


def get_current_user_no_refresh(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Same as get_current_user but does NOT rotate the cookie.

    Use for endpoints that need to know the current user but should not
    extend the idle window (e.g. logout).
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    payload = read_session(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    user = db.get(User, user_id)
    if user is None or user.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    return user


def get_current_user_optional(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Optional[User]:
    return _load_user_from_cookie(request, response, db)


def require_password_changed(
    user: User = Depends(get_current_user),
) -> User:
    if user.must_change_password == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="must change password",
        )
    return user
