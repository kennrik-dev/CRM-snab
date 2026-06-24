"""Derived calculations for the Сопровождение page (Phase 6.1).

Pure functions over duck-typed objects (ORM rows OR SimpleNamespace in tests).
Money is INTEGER kopecks; dates are ISO 'YYYY-MM-DD' strings; `today` is a
`date` injected by the caller (tests fix it; routers call today_moscow()).

Spec: docs/32-calculations.md §1–5. Decisions: docs/superpowers/plans/2026-06-24-phase6-soprovozhdenie-backend.md.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")

_DOC_KEYS = ("ttn", "m15", "upd", "sert")


def today_moscow() -> date:
    """Current calendar date in Europe/Moscow."""
    return datetime.now(MOSCOW).date()


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def position_sum(pos) -> int:
    """qty * price (kopecks). price None → 0. Fractional qty rounded to int."""
    qty = getattr(pos, "qty", 0) or 0
    price = getattr(pos, "price", None)
    if price is None:
        return 0
    return int(round(qty * price))


def procedure_sum(positions) -> int:
    """Σ position_sum."""
    return sum(position_sum(p) for p in positions)


def progress(positions, deliveries) -> tuple[int, int, float]:
    """(delivered, total, pct). total = #positions; delivered = #positions whose
    delivery is 'done'. pct = delivered/total*100 (0.0 if total==0)."""
    positions = list(positions)
    total = len(positions)
    done_ids = {d.id for d in deliveries if getattr(d, "status", None) == "done"}
    delivered = sum(1 for p in positions if getattr(p, "delivery_id", None) in done_ids)
    pct = (delivered / total * 100.0) if total else 0.0
    return delivered, total, pct


def is_delivery_overdue(delivery, srok_dd, today: date) -> bool:
    """transit AND contractual deadline (srok_dd) passed."""
    if getattr(delivery, "status", None) == "done":
        return False
    srok = _parse_date(srok_dd)
    return srok is not None and srok < today


def is_delivery_late(delivery, srok_dd, today: date) -> bool:
    """done but received (delivery.date) after srok_dd."""
    if getattr(delivery, "status", None) != "done":
        return False
    srok = _parse_date(srok_dd)
    d = _parse_date(getattr(delivery, "date", None))
    return srok is not None and d is not None and d > srok


def is_procedure_overdue(srok_dd, status_postavki, today: date) -> bool:
    """Deadline passed AND not fully delivered (Решение 2)."""
    srok = _parse_date(srok_dd)
    if srok is None or srok >= today:
        return False
    return status_postavki != "Поставлено"


def overdue_pct(positions, deliveries, srok_dd, today: date) -> float:
    """% positions in overdue-or-late deliveries (32§4). 0.0 if no positions."""
    positions = list(positions)
    total = len(positions)
    if total == 0:
        return 0.0
    by_id = {d.id: d for d in deliveries}
    late = 0
    for p in positions:
        d = by_id.get(getattr(p, "delivery_id", None))
        if d is None:
            continue
        if is_delivery_overdue(d, srok_dd, today) or is_delivery_late(d, srok_dd, today):
            late += 1
    return late / total * 100.0


def docs_aggregate(deliveries) -> dict:
    """Per doc flag: True iff set in ALL deliveries. No deliveries → all False."""
    deliveries = list(deliveries)
    if not deliveries:
        return {k: False for k in _DOC_KEYS}
    out = {}
    for k in _DOC_KEYS:
        attr = "doc_" + k
        out[k] = all(bool(getattr(d, attr, 0)) for d in deliveries)
    return out


def is_upd_overdue(upd, today: date) -> bool:
    """await AND upd.srok passed."""
    if getattr(upd, "pay_status", None) != "await":
        return False
    srok = _parse_date(getattr(upd, "srok", None))
    return srok is not None and srok < today


__all__ = [
    "today_moscow",
    "position_sum",
    "procedure_sum",
    "progress",
    "is_delivery_overdue",
    "is_delivery_late",
    "is_procedure_overdue",
    "overdue_pct",
    "docs_aggregate",
    "is_upd_overdue",
]
