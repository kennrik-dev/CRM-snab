"""Pydantic v2 schemas for /reports (Phase 9.1).

Generic report snapshot — one shape feeds JSON view + Excel/PDF/CSV export.
Money/date cells are pre-formatted strings (BE formats via _fmt_money/_fmt_date).
Spec: docs/15-page-otchety.md, docs/31 §6, docs/32 §8. Decisions: docs/superpowers/specs/2026-06-28-phase9-reports-design.md.
"""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class CellObj(BaseModel):
    """Styled cell. `text` is the export/plain render; FE uses kind + extras."""
    text: Optional[str] = None
    kind: Optional[str] = None     # claim|mono|text|stage|days|money|date|date-late|percent|note
    color: Optional[str] = None    # for kind='stage': token like '--proc'
    level: Optional[str] = None    # for kind='days': ''|'warn'|'bad'
    code: Optional[str] = None     # for kind='claim': parent code 'Т-67'
    title: Optional[str] = None    # for kind='claim': title


# A cell is either a plain string or a styled object.
Cell = Union[str, CellObj]


class Column(BaseModel):
    key: str
    label: str
    kind: Optional[str] = None
    align: Optional[str] = None    # 'left' | 'right'


class Section(BaseModel):
    title: Optional[str] = None
    columns: list[Column]
    rows: list[list[Cell]]
    footer: Optional[list[Cell]] = None


class Kpi(BaseModel):
    label: str
    value: str
    color: Optional[str] = None


class PeriodInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    key: str
    label: str
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None


class ReportOut(BaseModel):
    type: str
    title: str
    period: Optional[PeriodInfo] = None
    kpis: list[Kpi]
    sections: list[Section]


class FiltersOut(BaseModel):
    mtr: list[str]
    supplier: list[str]
    author: list[str]


__all__ = [
    "CellObj", "Cell", "Column", "Section", "Kpi", "PeriodInfo",
    "ReportOut", "FiltersOut",
]
