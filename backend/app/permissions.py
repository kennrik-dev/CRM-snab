"""Role / block / action permissions matrix + FastAPI guard.

Phase 3.1 — spec locked in `docs/03-roles-permissions.md` §3-§4.
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, status

from app.dependencies import require_password_changed
from app.models import User


# ---------------------------------------------------------------------------
# Block universe
# ---------------------------------------------------------------------------

ALL_BLOCKS = ("komplektaciya", "zakupka", "soprovozhdenie", "oplaty", "reports", "admin")

# Куратор отдела — владеет блоками своего отдела в полном объёме.
DEPT_BLOCKS_CURATOR = {
    "Комплектация": ("komplektaciya",),
    "Закупки":       ("zakupka",),
    "Сопровождение": ("soprovozhdenie", "oplaty"),
}

# Сотрудник отдела — только свой этап (по 02-statuses §7).
# Сотрудник Сопровождения НЕ владеет блоком «Оплаты».
DEPT_BLOCKS_EMPLOYEE = {
    "Комплектация": ("komplektaciya",),
    "Закупки":       ("zakupka",),
    "Сопровождение": ("soprovozhdenie",),
}

WORK_BLOCKS = ("komplektaciya", "zakupka", "soprovozhdenie", "oplaty")


# ---------------------------------------------------------------------------
# can() — pure permission check
# ---------------------------------------------------------------------------

def can(user: Optional[User], block: str, action: str) -> bool:
    """Return True iff `user` may perform `action` ("view" | "edit") on `block`."""
    # Rule 1: invalid inputs short-circuit to False.
    if user is None or block not in ALL_BLOCKS or action not in ("view", "edit"):
        return False

    # Rule 5: reports is read-only.
    if block == "reports" and action == "edit":
        return False

    # Rule 2: Админ — всё (включая admin-блок).
    if user.global_role == "Админ":
        return True

    # Rule 3: Руководитель — read-only, без admin-блока.
    if user.global_role == "Руководитель":
        if action == "edit":
            return False
        return block != "admin"

    # Rules 4: department users.
    if user.account_type == "department":
        is_curator = (user.is_curator == 1)
        dept = user.department
        owned = (
            DEPT_BLOCKS_CURATOR.get(dept, ())
            if is_curator
            else DEPT_BLOCKS_EMPLOYEE.get(dept, ())
        )

        if action == "edit":
            return block in owned

        # action == "view"
        if block == "admin":
            return False
        if block == "reports":
            return is_curator
        # рабочие блоки — все сотрудники отдела
        return block in WORK_BLOCKS

    # Any other case: deny by default.
    return False


# ---------------------------------------------------------------------------
# permissions_map() — for /auth/me and any other consumer
# ---------------------------------------------------------------------------

def permissions_map(user: User) -> dict:
    """Return {block: {"view": bool, "edit": bool}} for all 6 blocks."""
    return {
        block: {"view": can(user, block, "view"), "edit": can(user, block, "edit")}
        for block in ALL_BLOCKS
    }


# ---------------------------------------------------------------------------
# require_action() — FastAPI dependency
# ---------------------------------------------------------------------------

def require_action(block: str, action: str) -> Callable[..., User]:
    """Build a FastAPI dependency that enforces can(user, block, action).

    Depends on `require_password_changed` so must_change_password=1 → 403 first.
    """
    def _dep(user: User = Depends(require_password_changed)) -> User:
        if not can(user, block, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden",
            )
        return user

    return _dep


__all__ = [
    "ALL_BLOCKS",
    "DEPT_BLOCKS_CURATOR",
    "DEPT_BLOCKS_EMPLOYEE",
    "can",
    "permissions_map",
    "require_action",
]
