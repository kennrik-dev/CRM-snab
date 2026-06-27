"""Derived calculations for the Сопровождение page (Phase 6.1).

Pure functions over duck-typed objects (ORM rows OR SimpleNamespace in tests);
`payments_summary(db, today)` is the documented exception — it queries a db Session.
Money is INTEGER kopecks; dates are ISO 'YYYY-MM-DD' strings; `today` is a
`date` injected by the caller (tests fix it; routers call today_moscow()).

Spec: docs/32-calculations.md §1–5. Decisions: docs/superpowers/plans/2026-06-24-phase6-soprovozhdenie-backend.md.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_

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
    delivery is 'done' (получена). pct = delivered/total*100 (0.0 if total==0).
    Count-based (по числу позиций, не штук) — см. colonку «Поз.» списка сопровождения."""
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


def payments_summary(db, today: date) -> dict:
    """Сводка «Оплаты» (docs/32 §7). Суммы — int коп. (None-amount → 0).
    Исключает УПД отменённых процедур; manual-УПД (без процедуры) учитываются.

    Returns {"meters": {paid, await_, overdue, in_work},
             "bar": {paid, await_, delivered_no_upd, contracted_no_delivery}}.
    """
    from app.models import (
        Delivery, Procedure, ProcedurePosition, UpdPayment,
    )

    active = or_(
        Procedure.status_postavki.is_(None),
        Procedure.status_postavki != "Отменена",
    )

    upds = (
        db.query(UpdPayment)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id, isouter=True)
        .join(Procedure, Delivery.procedure_id == Procedure.id, isouter=True)
        .filter(active)
        .all()
    )
    paid = sum((u.amount or 0) for u in upds if u.pay_status == "paid")
    await_ = sum((u.amount or 0) for u in upds if u.pay_status == "await")
    overdue = sum(
        (u.amount or 0) for u in upds
        if u.pay_status == "await" and is_upd_overdue(u, today)
    )
    in_work = paid + await_

    # Поставки, покрытые УПД (есть upd_payment)
    covered = {u.delivery_id for u in upds if u.delivery_id is not None}

    active_proc_ids = {
        p.id for p in db.query(Procedure).filter(active).all()
    }
    procs_with_delivery = {
        d.procedure_id for d in
        db.query(Delivery).filter(Delivery.procedure_id.in_(active_proc_ids)).all()
    }

    delivered_no_upd = 0
    contracted_no_delivery = 0
    pos_rows = (
        db.query(ProcedurePosition)
        .filter(ProcedurePosition.procedure_id.in_(active_proc_ids))
        .all()
    )
    for p in pos_rows:
        s = position_sum(p)
        if p.delivery_id is not None and p.delivery_id not in covered:
            delivered_no_upd += s
        if p.procedure_id not in procs_with_delivery:
            contracted_no_delivery += s

    return {
        "meters": {"paid": paid, "await_": await_, "overdue": overdue, "in_work": in_work},
        "bar": {
            "paid": paid,
            "await_": await_,
            "delivered_no_upd": delivered_no_upd,
            "contracted_no_delivery": contracted_no_delivery,
        },
    }


def dashboard(db, today: date) -> dict:
    """Дашборд (docs/14, docs/32 §6). Stub — real sections land in Tasks 2–5."""
    return {
        "meters": [],
        "flow": [],
        "attention": [],
        "feed": [],
        "tables": {
            "awaiting": {"total": 0, "items": []},
            "procurement": {"total": 0, "items": []},
            "support": {"total": 0, "items": []},
        },
    }


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
    "payments_summary",
    "dashboard",
]
