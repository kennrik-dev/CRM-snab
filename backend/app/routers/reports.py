"""/reports router (Phase 9.1) — конструктор выгрузок (read-only).

Auth = require_action('reports','view') → Руководитель/Админ/Куратор; employee → 403.
Data is global (Куратор sees all). No write_audit (pure read).
Spec: docs/15-page-otchety.md, docs/31 §6, docs/32 §8. Decisions: docs/superpowers/specs/2026-06-28-phase9-reports-design.md.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import calculations as calc
from app.db import get_db
from app.models import User
from app.permissions import require_action
from app.schemas.reports import FiltersOut, ReportOut


router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_TYPES = ("time", "sums", "late", "people")
_BUILDERS = {
    "time": calc.report_time,
    "sums": calc.report_sums,
    "late": calc.report_late,
    "people": calc.report_people,
}


def _build_flt(period, date_from, date_to, mtr, supplier, author) -> dict:
    return {
        "period": period, "date_from": date_from, "date_to": date_to,
        "mtr": mtr, "supplier": supplier, "author": author,
    }


def _validate_period(flt: dict) -> None:
    """R12: custom requires a valid inclusive range. Unknown period → 422."""
    period = flt.get("period")
    if period is None:
        return
    if period not in ("month", "quarter", "year", "custom"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="unknown period")
    if period == "custom":
        f = calc._parse_date(flt.get("date_from"))
        t = calc._parse_date(flt.get("date_to"))
        if f is None or t is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="custom period requires date_from and date_to")
        if f > t:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="date_from must be <= date_to")


@router.get("", response_model=FiltersOut)
def get_filters(
    db: Session = Depends(get_db),
    _user: User = Depends(require_action("reports", "view")),
) -> FiltersOut:
    from app.models import ParentRequest, Procedure

    mtr_p = [r[0] for r in db.query(ParentRequest.mtr).filter(ParentRequest.mtr.isnot(None)).distinct()]
    mtr_pr = [r[0] for r in db.query(Procedure.mtr).filter(Procedure.mtr.isnot(None)).distinct()]
    suppliers = [r[0] for r in db.query(Procedure.supplier)
                 .filter(Procedure.supplier.isnot(None)).distinct().order_by(Procedure.supplier)]
    authors = [r[0] for r in db.query(ParentRequest.sostavitel)
               .filter(ParentRequest.sostavitel.isnot(None)).distinct().order_by(ParentRequest.sostavitel)]
    return FiltersOut(mtr=sorted(set(mtr_p + mtr_pr)), supplier=suppliers, author=authors)


@router.get("/{type}", response_model=ReportOut)
def get_report(
    type: str,
    period: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    mtr: Optional[str] = Query(default=None),
    supplier: Optional[str] = Query(default=None),
    author: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_action("reports", "view")),
) -> ReportOut:
    if type not in REPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown report type")
    flt = _build_flt(period, date_from, date_to, mtr, supplier, author)
    _validate_period(flt)
    snap = _BUILDERS[type](db, calc.today_moscow(), flt)
    return ReportOut(**snap)
