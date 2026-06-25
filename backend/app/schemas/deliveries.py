"""Pydantic v2 schemas for deliveries + support list (Phase 6.2)."""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class DeliveryUpdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    upd: Optional[str] = None
    pay_status: Optional[str] = None


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    n: int
    status: str
    date: Optional[str] = None
    eta: Optional[str] = None
    doc_ttn: int
    doc_m15: int
    doc_upd: int
    doc_sert: int
    upd: Optional[DeliveryUpdOut] = None


class DeliveryPositionIn(BaseModel):
    """Частичная отгрузка: id позиции + сколько отгружаем (0 < qty ≤ position.qty)."""
    id: int
    qty: float = Field(gt=0)


class DeliveryCreate(BaseModel):
    # Каждая запись: либо int (id позиции → отгрузить ВСЁ), либо {id, qty} (частично).
    # ≥1 записи; пустой список → 422 (Pydantic min_length).
    positions: list[Union[int, DeliveryPositionIn]] = Field(min_length=1)


class DeliveryPatch(BaseModel):
    status: Optional[str] = None       # 'done' (transit→done one-way)
    date: Optional[str] = None
    eta: Optional[str] = None
    doc_ttn: Optional[int] = None
    doc_m15: Optional[int] = None
    doc_upd: Optional[int] = None
    doc_sert: Optional[int] = None


class UpdIn(BaseModel):
    upd: str = Field(min_length=1)


class SupportListItem(BaseModel):
    id: int
    proc: Optional[str] = None
    tender_num: Optional[str] = None
    code: str
    title: str
    mtr: Optional[str] = None
    supplier: Optional[str] = None
    contract: Optional[str] = None
    contract_sum: Optional[int] = None
    status_sdelki: Optional[str] = None
    status_postavki: Optional[str] = None
    srok_dd: Optional[str] = None
    plan_date: Optional[str] = None
    fakt_date: Optional[str] = None
    # derived (server-computed via app.calculations)
    is_overdue: bool
    overdue_pct: float
    docs: dict
    progress_delivered: int
    progress_total: int
    created_at: str


class PaginatedSupport(BaseModel):
    items: list[SupportListItem]
    total: int


__all__ = [
    "DeliveryUpdOut", "DeliveryOut", "DeliveryCreate", "DeliveryPositionIn",
    "DeliveryPatch", "UpdIn", "SupportListItem", "PaginatedSupport",
]
