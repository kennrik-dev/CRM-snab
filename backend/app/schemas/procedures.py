"""Pydantic v2 schemas for /procurement + /procedures routers (Phase 5.1).

Locked spec from `docs/superpowers/plans/2026-06-23-phase5-zakupka.md` §5.1.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Position sub-schema
# ---------------------------------------------------------------------------

class ProcedurePositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    procedure_id: int
    source_id: Optional[int] = None
    name: str
    qty: float
    unit: Optional[str] = None
    gost_tu: Optional[str] = None
    doc_code: Optional[str] = None
    price: Optional[int] = None  # INTEGER kopecks


# ---------------------------------------------------------------------------
# List shapes
# ---------------------------------------------------------------------------

class ProcedureListItem(BaseModel):
    id: int
    proc: Optional[str] = None
    tender_num: Optional[str] = None     # tender.num (№ заявки)
    code: str                            # parent.code (Т-67)
    title: str                           # parent.title
    mtr: Optional[str] = None            # proc.mtr ?? parent.mtr
    supplier: Optional[str] = None
    fio_zakupshchik: Optional[str] = None
    pub_start: Optional[str] = None
    pub_end: Optional[str] = None
    zagruzka: str                        # parent.zagruzka
    position_count: int
    status_zakup: Optional[str] = None
    created_at: str


class PaginatedProcedures(BaseModel):
    items: list[ProcedureListItem]
    total: int


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

class ProcedureDetail(BaseModel):
    id: int
    proc: Optional[str] = None
    tender_id: int
    tender_num: Optional[str] = None
    parent_id: int
    code: str
    title: str
    mtr: Optional[str] = None
    supplier: Optional[str] = None
    fio_zakupshchik: Optional[str] = None
    pub_start: Optional[str] = None
    pub_end: Optional[str] = None
    zagruzka: str
    block: str
    status_zakup: Optional[str] = None
    created_at: str
    positions: list[ProcedurePositionOut] = []
    # NOTE: block_entered_at intentionally OMITTED (служебное)


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

class ProcedurePatch(BaseModel):
    proc: Optional[str] = None
    tender_num: Optional[str] = None     # writes tender.num
    supplier: Optional[str] = None
    fio_zakupshchik: Optional[str] = None
    mtr: Optional[str] = None
    pub_start: Optional[str] = None
    pub_end: Optional[str] = None
    status_zakup: Optional[str] = None   # validated against dict (6 values)


__all__ = [
    "ProcedurePositionOut",
    "ProcedureListItem",
    "PaginatedProcedures",
    "ProcedureDetail",
    "ProcedurePatch",
]
