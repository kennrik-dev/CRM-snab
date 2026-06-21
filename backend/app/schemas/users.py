"""Pydantic v2 schemas for the users (admin) endpoints."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Allowed values (mirror DB CHECK constraints in app.models.User)
# ---------------------------------------------------------------------------
ALLOWED_DEPARTMENTS = ("Комплектация", "Закупки", "Сопровождение")
ALLOWED_GLOBAL_ROLES = ("Админ", "Руководитель")


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class UserCreateRequest(BaseModel):
    email: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    account_type: str = Field(min_length=1)  # "department" or "global"
    department: Optional[str] = None
    is_curator: bool = False
    global_role: Optional[str] = None
    password: str = Field(min_length=1)


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    is_curator: Optional[bool] = None
    global_role: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    account_type: str
    department: Optional[str] = None
    is_curator: int
    global_role: Optional[str] = None
    is_active: int
    must_change_password: int
    created_at: str


class PaginatedUsersResponse(BaseModel):
    items: list[UserOut]
    total: int
