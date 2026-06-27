"""Pydantic v2 schemas for /dashboard (Phase 8.1).

Read-only overview payload. Money = INTEGER kopecks (FE formats); dates = ISO strings.
Spec: docs/14-page-dashboard.md, docs/32 §6. Decisions: docs/superpowers/specs/2026-06-27-phase8-dashboard-design.md.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SegBar(BaseModel):
    on: int
    total: int


class MeterOut(BaseModel):
    key: str
    label: str
    value: int
    unit: Optional[str] = None
    sub: Optional[str] = None      # text detail (e.g. "34 / 39 поставок")
    amount: Optional[int] = None   # kopecks detail (FE formats with money()) — used iff sub is None
    seg: SegBar
    color: str


class FlowStageOut(BaseModel):
    key: str
    label: str
    count: int
    sub: Optional[str] = None
    route: str
    color: str


class TargetOut(BaseModel):
    kind: str   # "procedure" | "payment" | "parent"
    id: int


class AttentionItemOut(BaseModel):
    id_label: str
    severity: str          # "error" | "warning"
    text: str
    target: TargetOut


class FeedItemOut(BaseModel):
    actor: str
    action_label: str
    entity_display: Optional[str] = None
    target: Optional[TargetOut] = None
    created_at: str


class AwaitingRowOut(BaseModel):
    id: int
    code: str
    title: str
    mtr: Optional[str] = None
    srok: Optional[str] = None
    position_count: int
    status: str


class ProcurementRowOut(BaseModel):
    id: int
    code: str
    title: str
    num: Optional[str] = None        # procedure.proc
    supplier: Optional[str] = None
    position_count: int
    status_zakup: Optional[str] = None


class SupportRowOut(BaseModel):
    id: int
    code: str
    title: str
    num: Optional[str] = None        # procedure.proc
    supplier: Optional[str] = None
    contract_sum: Optional[int] = None   # kopecks
    status_postavki: Optional[str] = None
    overdue_pct: float
    delivered: int
    total: int


class CompactAwaitingOut(BaseModel):
    total: int
    items: list[AwaitingRowOut]


class CompactProcurementOut(BaseModel):
    total: int
    items: list[ProcurementRowOut]


class CompactSupportOut(BaseModel):
    total: int
    items: list[SupportRowOut]


class DashboardTables(BaseModel):
    awaiting: CompactAwaitingOut
    procurement: CompactProcurementOut
    support: CompactSupportOut


class DashboardOut(BaseModel):
    meters: list[MeterOut]
    flow: list[FlowStageOut]
    attention: list[AttentionItemOut]
    feed: list[FeedItemOut]
    tables: DashboardTables


__all__ = [
    "SegBar", "MeterOut", "FlowStageOut", "TargetOut",
    "AttentionItemOut", "FeedItemOut",
    "AwaitingRowOut", "ProcurementRowOut", "SupportRowOut",
    "CompactAwaitingOut", "CompactProcurementOut", "CompactSupportOut",
    "DashboardTables", "DashboardOut",
]
