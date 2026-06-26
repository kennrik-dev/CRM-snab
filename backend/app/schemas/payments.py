"""Pydantic v2 schemas for /payments (Phase 7.1).

Money = INTEGER kopecks; dates = ISO 'YYYY-MM-DD' strings (Optional).
Spec: docs/31-api.md §5. Decisions: docs/superpowers/specs/2026-06-26-phase7-oplaty-design.md.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UpdPositionBase(BaseModel):
    n: Optional[int] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    qty: Optional[float] = None
    price: Optional[int] = None


class UpdPositionIn(UpdPositionBase):
    pass


class UpdPositionOut(UpdPositionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PaymentCreate(BaseModel):
    upd: str = Field(min_length=1)
    request_label: Optional[str] = None
    supplier: Optional[str] = None
    srok: Optional[str] = None
    amount: Optional[int] = None
    zrds: Optional[str] = None
    positions: Optional[list[UpdPositionIn]] = None


class PaymentPatch(BaseModel):
    srok: Optional[str] = None
    zrds: Optional[str] = None
    contract: Optional[str] = None
    supplier: Optional[str] = None
    amount: Optional[int] = None
    positions: Optional[list[UpdPositionIn]] = None


class PaymentListItem(BaseModel):
    id: int
    upd: str
    origin: str
    request_display: Optional[str] = None
    supplier: Optional[str] = None
    contract: Optional[str] = None
    zrds: Optional[str] = None
    delivery_n: Optional[int] = None
    pay_status: str
    is_overdue: bool
    srok: Optional[str] = None
    pay_date: Optional[str] = None
    amount: Optional[int] = None
    created_at: str


class PaginatedPayments(BaseModel):
    items: list[PaymentListItem]
    total: int


class PaymentDeliveryOut(BaseModel):
    n: int
    procedure_id: int
    parent_code: Optional[str] = None


class PaymentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    upd: str
    origin: str
    delivery_id: Optional[int] = None
    request_label: Optional[str] = None
    supplier: Optional[str] = None
    contract: Optional[str] = None
    zrds: Optional[str] = None
    srok: Optional[str] = None
    amount: Optional[int] = None
    pay_status: str
    pay_date: Optional[str] = None
    created_at: str
    positions: list[UpdPositionOut] = []
    delivery: Optional[PaymentDeliveryOut] = None
    is_overdue: bool


class SummaryMeters(BaseModel):
    paid: int
    await_: int
    overdue: int
    in_work: int


class SummaryBar(BaseModel):
    paid: int
    await_: int
    delivered_no_upd: int
    contracted_no_delivery: int


class PaymentsSummary(BaseModel):
    meters: SummaryMeters
    bar: SummaryBar


__all__ = [
    "UpdPositionBase", "UpdPositionIn", "UpdPositionOut",
    "PaymentCreate", "PaymentPatch", "PaymentListItem", "PaginatedPayments",
    "PaymentDeliveryOut", "PaymentDetail", "SummaryMeters", "SummaryBar",
    "PaymentsSummary",
]
