"""Pydantic schemas for /history (Phase 10 B3)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor: str
    created_at: str


class HistoryList(BaseModel):
    items: list[AuditEntryOut]
    total: int
