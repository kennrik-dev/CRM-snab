"""Pydantic v2 schemas for the auth endpoints."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember_me: bool = False


class ChangePasswordRequest(BaseModel):
    current: str = Field(min_length=1)
    new: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# User projection (returned by /auth/me)
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


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class MeResponse(BaseModel):
    user: UserOut
    permissions: dict
    must_change_password: bool


class OkResponse(BaseModel):
    ok: bool = True


class LoginResponse(BaseModel):
    ok: bool = True
    must_change_password: bool
