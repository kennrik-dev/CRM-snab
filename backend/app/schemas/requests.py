"""Pydantic v2 schemas for /requests router (Phase 4.1).

Locked spec from `docs/31-api.md` §2 and `docs/02-statuses.md` §7.1.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Position sub-schemas
# ---------------------------------------------------------------------------

class RequestPositionIn(BaseModel):
    """Body for a single position in POST /requests and POST /requests/{id}/positions."""
    name: str = Field(min_length=1)
    qty: float
    unit: Optional[str] = None
    gost_tu: Optional[str] = None
    doc_code: Optional[str] = None


class RequestPositionPatch(BaseModel):
    """Partial update for PATCH /requests/{id}/positions/{pos_id}."""
    name: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None
    gost_tu: Optional[str] = None
    doc_code: Optional[str] = None


class PositionOut(BaseModel):
    """Response shape for a single position row."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int
    name: str
    qty: float
    unit: Optional[str] = None
    gost_tu: Optional[str] = None
    doc_code: Optional[str] = None


# ---------------------------------------------------------------------------
# ProcedureOut — minimal shape for /requests/{id} (tender's procedures)
# ---------------------------------------------------------------------------

class ProcedureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_id: int
    proc: Optional[str] = None
    supplier: Optional[str] = None
    block: str
    status_zakup: Optional[str] = None
    status_postavki: Optional[str] = None
    status_sdelki: Optional[str] = None


# ---------------------------------------------------------------------------
# TenderOut — minimal shape with embedded procedures
# ---------------------------------------------------------------------------

class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int
    num: Optional[str] = None
    procedures: list[ProcedureOut] = []


# ---------------------------------------------------------------------------
# Request create / patch
# ---------------------------------------------------------------------------

class RequestCreate(BaseModel):
    """Body for POST /requests — create a parent + positions."""
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    mtr: Optional[str] = None
    srok: Optional[str] = None
    dept: Optional[str] = None
    positions: list[RequestPositionIn] = []


class RequestPatch(BaseModel):
    """Body for PATCH /requests/{id} — partial update."""
    title: Optional[str] = None
    mtr: Optional[str] = None
    srok: Optional[str] = None
    dept: Optional[str] = None


class RequestDuplicate(BaseModel):
    """Body for POST /requests/{id}/duplicate."""
    code: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------

class RequestOut(BaseModel):
    """Full request (with embedded positions + tenders) — used for GET/{id},
    POST, PATCH, cancel/uncancel/duplicate responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    mtr: Optional[str] = None
    srok: Optional[str] = None
    zagruzka: str
    sostavitel: str
    created_by: Optional[int] = None
    dept: Optional[str] = None
    status: str
    created_at: str
    positions: list[PositionOut] = []
    tenders: list[TenderOut] = []


class RequestListItem(BaseModel):
    """Shorter shape for the list endpoint (GET /requests)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    mtr: Optional[str] = None
    srok: Optional[str] = None
    zagruzka: str
    sostavitel: str
    status: str
    created_at: str
    position_count: int


class PaginatedRequests(BaseModel):
    items: list[RequestListItem]
    total: int


__all__ = [
    "RequestPositionIn",
    "RequestPositionPatch",
    "PositionOut",
    "ProcedureOut",
    "TenderOut",
    "RequestCreate",
    "RequestPatch",
    "RequestDuplicate",
    "RequestOut",
    "RequestListItem",
    "PaginatedRequests",
]