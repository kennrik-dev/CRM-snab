"""Pydantic schemas for /comments (Phase 10 B2). Mirror backend columns."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    target_kind: Literal["parent", "tender", "procedure"]
    target_id: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_kind: str
    target_id: int
    author_id: Optional[int] = None
    author: Optional[str] = None
    role: Optional[str] = None
    text: str
    created_at: str


class CommentList(BaseModel):
    items: list[CommentOut]
    total: int
