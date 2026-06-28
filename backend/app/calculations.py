"""Derived calculations for the Сопровождение page (Phase 6.1).

Pure functions over duck-typed objects (ORM rows OR SimpleNamespace in tests);
`payments_summary(db, today)` is the documented exception — it queries a db Session.
Money is INTEGER kopecks; dates are ISO 'YYYY-MM-DD' strings; `today` is a
`date` injected by the caller (tests fix it; routers call today_moscow()).

Spec: docs/32-calculations.md §1–5. Decisions: docs/superpowers/plans/2026-06-24-phase6-soprovozhdenie-backend.md.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_

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


# ---------------------------------------------------------------------------
# Dashboard (Phase 8.1) — docs/14, docs/32 §6
# ---------------------------------------------------------------------------

_DASH_DOC_NAMES = {"ttn": "ТТН", "m15": "М-15", "upd": "УПД"}

# (entity_kind, action) -> human phrase; entity_display is appended by the FE.
_AUDIT_PHRASES = {
    ("parent", "create"): "создал(а) заявку",
    ("parent", "update"): "обновил(а) заявку",
    ("parent", "cancel"): "отменил(а) заявку",
    ("parent", "uncancel"): "восстановил(а) заявку",
    ("parent", "duplicate"): "скопировал(а) заявку",
    ("parent", "positions_add"): "добавил(а) позиции в заявку",
    ("parent_request", "take_to_work"): "взял(а) в работу заявку",
    ("position", "position_update"): "изменил(а) позицию",
    ("position", "position_delete"): "удалил(а) позицию",
    ("procedure", "split"): "разбил(а) по поставщикам процедуру",
    ("procedure", "to_support"): "передал(а) в сопровождение процедуру",
    ("procedure", "cancel"): "отменил(а) процедуру",
    ("procedure", "uncancel"): "восстановил(а) процедуру",
    ("procedure", "update"): "обновил(а) процедуру",
    ("procedure", "positions_add"): "добавил(а) позиции в процедуру",
    ("procedure", "position_update"): "изменил(а) позицию в процедуре",
    ("procedure", "position_delete"): "удалил(а) позицию из процедуры",
    ("procedure", "delivery_create"): "создал(а) поставку в процедуре",
    ("procedure", "delivery_delete"): "удалил(а) поставку из процедуры",
    ("procedure", "delivery_update"): "изменил(а) поставку в процедуре",
    ("procedure", "upd_create"): "выставил(а) УПД для процедуры",
    ("procedure", "upd_update"): "обновил(а) УПД для процедуры",
    ("upd_payment", "payment_create"): "добавил(а) УПД",
    ("upd_payment", "payment_patch"): "изменил(а) УПД",
    ("upd_payment", "payment_pay"): "провёл(а) оплату по УПД",
}


def _fmt_money(kopecks: int) -> str:
    """ru-RU '1 500 ₽' / '1 500,5 ₽' / '12 345,67 ₽' (NBSP thousands, ',' decimal)."""
    rub = (kopecks or 0) / 100
    sign = "-" if rub < 0 else ""
    s = f"{abs(rub):.2f}"
    int_part, frac = s.split(".")
    int_part = f"{int(int_part):,}".replace(",", " ")
    frac = frac.rstrip("0")
    if frac:
        return f"{sign}{int_part},{frac} ₽"
    return f"{sign}{int_part} ₽"


def _fmt_date(value) -> str:
    """ISO 'YYYY-MM-DD' → 'ДД.ММ.ГГ'. None/invalid → ''."""
    d = _parse_date(value)
    if d is None:
        return ""
    return f"{d.day:02d}.{d.month:02d}.{str(d.year)[2:]}"


def is_procedure_completed(proc, upds) -> bool:
    """Завершённая процедура (Phase 6 R6): Поставлено AND ≥1 УПД AND all paid."""
    if getattr(proc, "status_postavki", None) != "Поставлено":
        return False
    if not upds:
        return False
    return all(getattr(u, "pay_status", None) == "paid" for u in upds)


def proc_sum(proc, positions) -> int:
    """contract_sum если задана, иначе Σ position_sum (коп.)."""
    cs = getattr(proc, "contract_sum", None)
    if cs is not None:
        return int(cs)
    return procedure_sum(positions)


def _seg(ratio: float) -> dict:
    on = max(0, min(14, round(ratio * 14)))
    return {"on": on, "total": 14}


def _load_dashboard_ctx(db, today: date):
    """Load + derive everything meters/flow/attention/tables need (compute once)."""
    from app.models import (
        Delivery, ParentRequest, Procedure, ProcedurePosition, Tender, UpdPayment,
    )

    active = or_(
        Procedure.status_postavki.is_(None),
        Procedure.status_postavki != "Отменена",
    )

    procs = db.query(Procedure).all()
    proc_ids = [p.id for p in procs]

    parent_map: dict = {}
    if proc_ids:
        rows = (
            db.query(Procedure.id, ParentRequest.code, ParentRequest.title)
            .join(Tender, Procedure.tender_id == Tender.id)
            .join(ParentRequest, Tender.parent_id == ParentRequest.id)
            .filter(Procedure.id.in_(proc_ids))
            .all()
        )
        for pid, code, title in rows:
            parent_map[pid] = {"code": code, "title": title}

    deliveries = (
        db.query(Delivery).filter(Delivery.procedure_id.in_(proc_ids)).all()
        if proc_ids else []
    )
    positions = (
        db.query(ProcedurePosition).filter(ProcedurePosition.procedure_id.in_(proc_ids)).all()
        if proc_ids else []
    )
    upds = (
        db.query(UpdPayment)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id, isouter=True)
        .join(Procedure, Delivery.procedure_id == Procedure.id, isouter=True)
        .filter(active)
        .all()
    )

    deliveries_by_proc = defaultdict(list)
    for d in deliveries:
        deliveries_by_proc[d.procedure_id].append(d)
    positions_by_proc = defaultdict(list)
    for p in positions:
        positions_by_proc[p.procedure_id].append(p)
    delivery_proc = {d.id: d.procedure_id for d in deliveries}
    upds_by_proc = defaultdict(list)
    for u in upds:
        pid = delivery_proc.get(u.delivery_id)
        if pid is not None:
            upds_by_proc[pid].append(u)

    completed_proc_ids = set()
    for p in procs:
        if is_procedure_completed(p, upds_by_proc.get(p.id, [])):
            completed_proc_ids.add(p.id)

    active_zakup = [
        p for p in procs
        if p.block == "zakupka" and p.status_zakup != "Отменена"
    ]
    supp_procs = [
        p for p in procs
        if p.block == "soprovozhdenie"
        and p.status_postavki != "Отменена"
        and p.id not in completed_proc_ids
    ]
    active_total = len(active_zakup) + len(supp_procs)
    overdue_procs = [
        p for p in supp_procs
        if is_procedure_overdue(p.srok_dd, p.status_postavki, today)
    ]

    # on-time deliveries (across active support procs; cancelled procs already
    # excluded because their deliveries belong to a procedure we still load —
    # but we only count deliveries of supp_procs to honour 'Отменена excluded').
    on_time = 0
    all_deliveries = 0
    for p in supp_procs:
        for d in deliveries_by_proc.get(p.id, []):
            all_deliveries += 1
            if getattr(d, "status", None) == "done" and not is_delivery_late(d, p.srok_dd, today):
                on_time += 1

    await_upds = [u for u in upds if u.pay_status == "await"]
    overdue_upds = [u for u in await_upds if is_upd_overdue(u, today)]
    all_active_upd = len(upds)

    # awaiting parents (no tender, status='awaiting') — global
    awaiting_count = (
        db.query(ParentRequest)
        .filter(ParentRequest.status == "awaiting")
        .filter(~db.query(Tender).filter(Tender.parent_id == ParentRequest.id).exists())
        .count()
    )

    return SimpleNamespace(
        today=today, procs=procs, parent_map=parent_map,
        deliveries=deliveries, deliveries_by_proc=deliveries_by_proc,
        positions_by_proc=positions_by_proc, upds=upds, upds_by_proc=upds_by_proc,
        completed_proc_ids=completed_proc_ids, delivery_proc=delivery_proc,
        active_zakup=active_zakup, supp_procs=supp_procs, active_total=active_total,
        overdue_procs=overdue_procs, on_time=on_time, all_deliveries=all_deliveries,
        await_upds=await_upds, overdue_upds=overdue_upds, all_active_upd=all_active_upd,
        awaiting_count=awaiting_count,
    )


def _dash_meters(ctx) -> list:
    active_total = ctx.active_total

    def ratio(n, d):
        return (n / d) if d else 0.0

    return [
        {
            "key": "in_zakupka", "label": "В закупке",
            "value": len(ctx.active_zakup), "unit": None,
            "sub": "процедур", "amount": None,
            "seg": _seg(ratio(len(ctx.active_zakup), active_total)), "color": "--proc",
        },
        {
            "key": "in_support", "label": "В сопровождении",
            "value": len(ctx.supp_procs), "unit": None,
            "sub": None,
            "amount": sum((p.contract_sum or 0) for p in ctx.supp_procs),
            "seg": _seg(ratio(len(ctx.supp_procs), active_total)), "color": "--supp",
        },
        {
            "key": "on_time_pct", "label": "Поставки в срок",
            "value": (round(ctx.on_time / ctx.all_deliveries * 100) if ctx.all_deliveries else 0),
            "unit": "%",
            "sub": f"{ctx.on_time} / {ctx.all_deliveries} поставок", "amount": None,
            "seg": _seg(ratio((ctx.on_time / ctx.all_deliveries * 100) if ctx.all_deliveries else 0, 100)),
            "color": "--ok",
        },
        {
            "key": "overdue", "label": "Просрочено",
            "value": len(ctx.overdue_procs), "unit": None,
            "sub": None,
            "amount": sum(proc_sum(p, ctx.positions_by_proc.get(p.id, [])) for p in ctx.overdue_procs),
            "seg": _seg(ratio(len(ctx.overdue_procs), active_total)), "color": "--late",
        },
        {
            "key": "upd_await", "label": "УПД в оплате",
            "value": len(ctx.await_upds), "unit": None,
            "sub": None,
            "amount": sum((u.amount or 0) for u in ctx.await_upds),
            "seg": _seg(ratio(len(ctx.await_upds), ctx.all_active_upd)), "color": "--pay",
        },
        {
            "key": "upd_overdue", "label": "УПД просрочено",
            "value": len(ctx.overdue_upds), "unit": None,
            "sub": None,
            "amount": sum((u.amount or 0) for u in ctx.overdue_upds),
            "seg": _seg(ratio(len(ctx.overdue_upds), len(ctx.await_upds))), "color": "--late",
        },
    ]


def _dash_flow(ctx) -> list:
    return [
        {"key": "awaiting", "label": "Ожидают закупки", "count": ctx.awaiting_count,
         "sub": None, "route": "/komplektaciya", "color": "--wait"},
        {"key": "procurement", "label": "В закупке", "count": len(ctx.active_zakup),
         "sub": None, "route": "/zakupka", "color": "--proc"},
        {"key": "support", "label": "В сопровождении", "count": len(ctx.supp_procs),
         "sub": None, "route": "/soprovozhdenie", "color": "--supp"},
        {"key": "payments", "label": "Оплаты", "count": len(ctx.await_upds),
         "sub": None, "route": "/oplaty", "color": "--pay"},
    ]


def _dash_attention(ctx) -> list:
    """«Требует внимания» (spec §6): 2 tiers, errors first by days desc, then warnings."""
    today = ctx.today
    items = []  # each: (severity_rank, days, item_dict)

    def label(p):
        code = ctx.parent_map.get(p.id, {}).get("code")
        if code and p.proc:
            return f"{code} · {p.proc}"
        return p.proc or code or "—"

    # 1. overdue / late deliveries (error)
    for p in ctx.supp_procs:
        for d in ctx.deliveries_by_proc.get(p.id, []):
            overdue = is_delivery_overdue(d, p.srok_dd, today)
            late = is_delivery_late(d, p.srok_dd, today)
            if not (overdue or late):
                continue
            srok = _parse_date(p.srok_dd)
            if late:
                ddate = _parse_date(getattr(d, "date", None))
                days = (ddate - srok).days if (srok and ddate) else 0
            else:
                days = (today - srok).days if srok else 0
            items.append((0, days, {
                "id_label": label(p),
                "severity": "error",
                "text": f"Поставка №{d.n} ({p.supplier or '—'}) — просрочена на {days} дн.",
                "target": {"kind": "procedure", "id": p.id},
            }))

    # 2. overdue payments (error)
    for u in ctx.overdue_upds:
        srok = _parse_date(getattr(u, "srok", None))
        days = (today - srok).days if srok else 0
        items.append((0, days, {
            "id_label": f"УПД {u.upd}",
            "severity": "error",
            "text": f"УПД {u.upd} просрочена к оплате +{days} дн. · {_fmt_money(u.amount or 0)}",
            "target": {"kind": "payment", "id": u.id},
        }))

    # 3. missing documents (error) — proc has ≥1 delivery, ttn/m15/upd not received in all
    for p in ctx.supp_procs:
        dels = ctx.deliveries_by_proc.get(p.id, [])
        if not dels:
            continue
        agg = docs_aggregate(dels)
        missing = [name for key, name in _DASH_DOC_NAMES.items() if not agg[key]]
        if missing:
            items.append((0, 0, {
                "id_label": label(p),
                "severity": "error",
                "text": "Документы не получены: " + ", ".join(missing),
                "target": {"kind": "procedure", "id": p.id},
            }))

    # 4. УПД without certificate (warning) — await delivery-УПД with doc_sert=0
    for u in ctx.await_upds:
        if u.delivery_id is None:
            continue
        d = next((x for x in ctx.deliveries if x.id == u.delivery_id), None)
        if d is not None and not bool(getattr(d, "doc_sert", 0)):
            items.append((1, 0, {
                "id_label": f"УПД {u.upd}",
                "severity": "warning",
                "text": f"УПД {u.upd} без сертификата — оплату можно провести",
                "target": {"kind": "payment", "id": u.id},
            }))

    items.sort(key=lambda t: (t[0], -t[1]))
    return [it for _, _, it in items]


def _dash_feed(db) -> list:
    """«Лента событий» (spec §7): last 20 audit_log, newest first."""
    from app.models import (
        AuditLog, ParentRequest, Procedure, Tender, UpdPayment, User,
    )

    rows = (
        db.query(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(20)
        .all()
    )

    # polymorphic entity display: batch-lookup codes per kind
    parent_ids = {r[0].entity_id for r in rows if r[0].entity_kind in ("parent", "parent_request")}
    proc_ids = {r[0].entity_id for r in rows if r[0].entity_kind == "procedure"}
    upd_ids = {r[0].entity_id for r in rows if r[0].entity_kind == "upd_payment"}

    code_map = {pid: code for pid, code in
                db.query(ParentRequest.id, ParentRequest.code)
                .filter(ParentRequest.id.in_(parent_ids)).all()} if parent_ids else {}
    # procedure rows: identify the procedure (proc, else parent-code fallback) AND its
    # block, so the feed always names which procedure + which department (user request).
    _BLOCK_RU = {"zakupka": "закупка", "soprovozhdenie": "сопровождение"}
    proc_info = {}
    if proc_ids:
        prow = (db.query(Procedure.id, Procedure.proc, Procedure.block, Tender.parent_id)
                .outerjoin(Tender, Procedure.tender_id == Tender.id)
                .filter(Procedure.id.in_(proc_ids)).all())
        pp_ids = {p[3] for p in prow if p[3] is not None}
        pp_codes = {i: c for i, c in
                    db.query(ParentRequest.id, ParentRequest.code)
                    .filter(ParentRequest.id.in_(pp_ids)).all()} if pp_ids else {}
        for pid, pproc, pblock, parent_id in prow:
            ident = pproc or pp_codes.get(parent_id) or f"#{pid}"
            br = _BLOCK_RU.get(pblock or "", "")
            proc_info[pid] = f"{ident} ({br})" if br else ident
    upd_map = {uid: upd for uid, upd in
               db.query(UpdPayment.id, UpdPayment.upd)
               .filter(UpdPayment.id.in_(upd_ids)).all()} if upd_ids else {}

    _TARGET_KIND = {"parent": "parent", "parent_request": "parent",
                    "procedure": "procedure", "upd_payment": "payment"}

    out = []
    for log, full_name in rows:
        kind = log.entity_kind
        if kind in ("parent", "parent_request"):
            display = code_map.get(log.entity_id)
        elif kind == "procedure":
            display = proc_info.get(log.entity_id)
        elif kind == "upd_payment":
            display = upd_map.get(log.entity_id)
        else:
            display = None
        tk = _TARGET_KIND.get(kind)
        out.append({
            "actor": full_name or "Система",
            "action_label": _AUDIT_PHRASES.get((kind, log.action), log.action),
            "entity_display": display,
            "target": {"kind": tk, "id": log.entity_id} if tk else None,
            "created_at": log.created_at,
        })
    return out


def _dash_tables(db, ctx) -> dict:
    """Compact tables (spec §8): top-10 newest, true total."""
    from app.models import ParentRequest, RequestedPosition, Tender

    # --- awaiting (parents: awaiting, no tender) ---
    aw_q = (
        db.query(ParentRequest)
        .filter(ParentRequest.status == "awaiting")
        .filter(~db.query(Tender).filter(Tender.parent_id == ParentRequest.id).exists())
    )
    aw_total = aw_q.count()
    aw_parents = aw_q.order_by(ParentRequest.created_at.desc(), ParentRequest.id.desc()).limit(10).all()
    aw_pos = {pid: c for pid, c in
              db.query(RequestedPosition.parent_id, func.count(RequestedPosition.id))
              .filter(RequestedPosition.parent_id.in_([p.id for p in aw_parents] or [0]))
              .group_by(RequestedPosition.parent_id).all()}
    awaiting_items = [{
        "id": p.id, "code": p.code, "title": p.title, "mtr": p.mtr, "srok": p.srok,
        "position_count": aw_pos.get(p.id, 0), "status": "Ожидает",
    } for p in aw_parents]

    # --- procurement (block=zakupka, status_zakup != Отменена) ---
    pr_procs = sorted(ctx.active_zakup, key=lambda p: (p.created_at, p.id), reverse=True)[:10]
    pr_pos = {pid: len(ctx.positions_by_proc.get(pid, [])) for pid in [p.id for p in pr_procs]}
    procurement_items = [{
        "id": p.id,
        "code": ctx.parent_map.get(p.id, {}).get("code"),
        "title": ctx.parent_map.get(p.id, {}).get("title"),
        "num": p.proc, "supplier": p.supplier,
        "position_count": pr_pos.get(p.id, 0), "status_zakup": p.status_zakup,
    } for p in pr_procs]

    # --- support (supp_procs) ---
    su_procs = sorted(ctx.supp_procs, key=lambda p: (p.created_at, p.id), reverse=True)[:10]
    support_items = []
    for p in su_procs:
        positions = ctx.positions_by_proc.get(p.id, [])
        deliveries = ctx.deliveries_by_proc.get(p.id, [])
        delivered, total, _pct = progress(positions, deliveries)
        support_items.append({
            "id": p.id,
            "code": ctx.parent_map.get(p.id, {}).get("code"),
            "title": ctx.parent_map.get(p.id, {}).get("title"),
            "num": p.proc, "supplier": p.supplier,
            "contract_sum": proc_sum(p, positions),
            "status_postavki": p.status_postavki,
            "overdue_pct": overdue_pct(positions, deliveries, p.srok_dd, ctx.today),
            "delivered": delivered, "total": total,
        })

    return {
        "awaiting": {"total": aw_total, "items": awaiting_items},
        "procurement": {"total": len(ctx.active_zakup), "items": procurement_items},
        "support": {"total": len(ctx.supp_procs), "items": support_items},
    }


def dashboard(db, today: date) -> dict:
    """Дашборд (docs/14, docs/32 §6). Разделы attention/feed/tables — в Задачах 3–5."""
    ctx = _load_dashboard_ctx(db, today)
    return {
        "meters": _dash_meters(ctx),
        "flow": _dash_flow(ctx),
        "attention": _dash_attention(ctx),
        "feed": _dash_feed(db),
        "tables": _dash_tables(db, ctx),
    }


# ---------------------------------------------------------------------------
# Reports (Phase 9.1) — docs/15, docs/32 §8
# ---------------------------------------------------------------------------

# --- shared cell/snapshot helpers (Phase 9.1) ----------------------------------

def _claim(code, title):
    return {"kind": "claim", "code": code or "—", "title": title or ""}


def _stage(text, color):
    return {"kind": "stage", "text": text, "color": color}


def _stage_for_block(block):
    if block == "zakupka":
        return _stage("В закупке", "--proc")
    if block == "soprovozhdenie":
        return _stage("В сопровождении", "--supp")
    return _stage("—", "--muted")


def _days(n: int):
    level = "bad" if n >= 14 else "warn" if n >= 10 else ""
    return {"kind": "days", "text": f"{n} дн.", "level": level}


def _money(kopecks):
    return {"kind": "money", "text": _fmt_money(kopecks)}


def _pct(value):
    return {"kind": "percent", "text": f"{round(value)}%"}


def _date_late(iso):
    return {"kind": "date-late", "text": _fmt_date(iso) or "—"}


def _kpi(label, value, color=None):
    return {"label": label, "value": value, "color": color}


def _snapshot(report_type, title, ctx, kpis, sections):
    return {
        "type": report_type, "title": title,
        "period": ctx.period_info, "kpis": kpis, "sections": sections,
    }


def report_time(db, today: date, flt: dict) -> dict:
    """Время на этапе / зависания (spec R4/R8)."""
    ctx = _load_report_ctx(db, today, flt)
    today = ctx.today
    rows = []
    # active procedures (not completed, not Отменена, has block_entered_at)
    for p in ctx.procs:
        if p.id in ctx.completed_proc_ids:
            continue
        if p.status_zakup == "Отменена" or p.status_postavki == "Отменена":
            continue
        bea = _parse_date(p.block_entered_at)
        if bea is None:
            continue
        days = (today - bea).days
        par = ctx.parent_by_proc.get(p.id, {})
        rows.append({
            "claim": _claim(par.get("code"), par.get("title")),
            "num": p.proc or "—",
            "supplier": p.supplier or "—",
            "stage": _stage_for_block(p.block),
            "days": _days(days),
            "srok": _fmt_date(p.srok_dd) or "—",
            "_days": days,
        })
    # awaiting parents stuck in Комплектация
    for par in ctx.awaiting_parents:
        zg = _parse_date(par.zagruzka)
        days = (today - zg).days if zg else 0
        rows.append({
            "claim": _claim(par.code, par.title),
            "num": "—",
            "supplier": "—",
            "stage": _stage("Комплектация", "--wait"),
            "days": _days(days),
            "srok": _fmt_date(par.srok) or "—",
            "_days": days,
        })
    rows.sort(key=lambda r: r["_days"], reverse=True)
    stuck = sum(1 for r in rows if r["_days"] >= 3)
    avg = round(sum(r["_days"] for r in rows) / len(rows)) if rows else 0
    kpis = [
        _kpi("Заявок в работе", str(len(rows))),
        _kpi("Зависли ≥3 дн.", str(stuck), "--late"),
        _kpi("Ср. время на этапе", f"{avg} дн."),
    ]
    columns = [
        {"key": "claim", "label": "Заявка", "kind": "claim", "align": "left"},
        {"key": "num", "label": "№", "kind": "mono", "align": "left"},
        {"key": "supplier", "label": "Поставщик", "kind": "text", "align": "left"},
        {"key": "stage", "label": "Этап", "kind": "stage", "align": "left"},
        {"key": "days", "label": "Дней на этапе", "kind": "days", "align": "right"},
        {"key": "srok", "label": "Срок поставки", "kind": "date", "align": "left"},
    ]
    rendered = [[r["claim"], r["num"], r["supplier"], r["stage"], r["days"], r["srok"]] for r in rows]
    section = {"title": None, "columns": columns, "rows": rendered, "footer": None}
    return _snapshot("time", "Время на этапе и зависания", ctx, kpis, [section])


def report_sums(db, today: date, flt: dict) -> dict:
    """Суммы по этапам и поставщикам (spec R5/R8). Completed included."""
    ctx = _load_report_ctx(db, today, flt)
    stage = {"zakupka": [0, 0], "soprovozhdenie": [0, 0]}  # [count, sum_kop]
    by_supp: dict = {}
    total = 0
    for p in ctx.procs:
        if p.status_zakup == "Отменена" or p.status_postavki == "Отменена":
            continue
        s = proc_sum(p, ctx.positions_by_proc.get(p.id, []))
        if p.block in stage:
            stage[p.block][0] += 1
            stage[p.block][1] += s
        total += s
        if p.supplier:
            by_supp.setdefault(p.supplier, [0, 0])
            by_supp[p.supplier][0] += 1
            by_supp[p.supplier][1] += s
    pay_total = sum((u.amount or 0) for u in ctx.upds if u.pay_status == "await")
    kpis = [
        _kpi("Всего по договорам", _fmt_money(total)),
        _kpi("В сопровождении", _fmt_money(stage["soprovozhdenie"][1]), "--supp"),
        _kpi("В оплате", _fmt_money(pay_total), "--pay"),
    ]
    cols1 = [
        {"key": "stage", "label": "Этап", "kind": "stage", "align": "left"},
        {"key": "n", "label": "Заявок", "kind": "num", "align": "right"},
        {"key": "sum", "label": "Сумма договоров", "kind": "money", "align": "right"},
    ]

    def stage_row(block, label, color):
        c, s = stage[block]
        return [_stage(label, color), str(c), _money(s)]

    rows1 = [
        stage_row("zakupka", "В закупке", "--proc"),
        stage_row("soprovozhdenie", "В сопровождении", "--supp"),
    ]
    footer1 = ["Итого", str(stage["zakupka"][0] + stage["soprovozhdenie"][0]), _money(total)]
    sec1 = {"title": None, "columns": cols1, "rows": rows1, "footer": footer1}

    cols2 = [
        {"key": "sup", "label": "Поставщик", "kind": "text", "align": "left"},
        {"key": "n", "label": "Кол-во", "kind": "num", "align": "right"},
        {"key": "sum", "label": "Сумма", "kind": "money", "align": "right"},
    ]
    rows2 = [[sup, str(c), _money(s)]
             for sup, (c, s) in sorted(by_supp.items(), key=lambda kv: kv[1][1], reverse=True)]
    sec2 = {"title": "По поставщикам", "columns": cols2, "rows": rows2, "footer": None}

    return _snapshot("sums", "Суммы по этапам и поставщикам", ctx, kpis, [sec1, sec2])


def report_late(db, today: date, flt: dict) -> dict:
    """Просрочки: поставки и оплаты. Stub — real in Task 5."""
    return {"type": "late", "title": "Просрочки: поставки и оплаты",
            "period": None, "kpis": [], "sections": []}


def report_people(db, today: date, flt: dict) -> dict:
    """Сводка по составителям/отделам. Stub — real in Task 6."""
    return {"type": "people", "title": "Сводка по составителям/отделам",
            "period": None, "kpis": [], "sections": []}


def _resolve_period(flt: dict, today: date):
    """(from_d, to_d, period_info|None). None period → (None,None,None)."""
    period = flt.get("period")
    if not period:
        return None, None, None
    if period == "custom":
        f = _parse_date(flt.get("date_from"))
        t = _parse_date(flt.get("date_to"))
        return f, t, {"key": "custom", "label": "Произвольный",
                      "from": flt.get("date_from") or "", "to": flt.get("date_to") or ""}
    if period == "month":
        from datetime import date as _date
        f = _date(today.year, today.month, 1); label = "Текущий месяц"
    elif period == "quarter":
        from datetime import date as _date
        qm = ((today.month - 1) // 3) * 3 + 1
        f = _date(today.year, qm, 1); label = "Квартал"
    elif period == "year":
        from datetime import date as _date
        f = _date(today.year, 1, 1); label = "С начала года"
    else:
        return None, None, None
    return f, today, {"key": period, "label": label, "from": f.isoformat(), "to": today.isoformat()}


def _load_report_ctx(db, today: date, flt: dict):
    """Filtered universe shared by all 4 report builders (spec R3/R6/R8)."""
    from app.models import (
        Delivery, ParentRequest, Procedure, ProcedurePosition, Tender, UpdPayment,
    )

    from_d, to_d, period_info = _resolve_period(flt, today)
    has_period = from_d is not None
    mtr = flt.get("mtr")
    supplier = flt.get("supplier")
    author = flt.get("author")

    def in_period(zagruzka_iso):
        if not has_period:
            return True
        zg = _parse_date(zagruzka_iso)
        return zg is not None and from_d <= zg <= to_d

    rows = (
        db.query(Procedure, ParentRequest)
        .join(Tender, Procedure.tender_id == Tender.id)
        .join(ParentRequest, Tender.parent_id == ParentRequest.id)
        .all()
    )
    procs: list = []
    parent_by_proc: dict = {}
    for p, par in rows:
        eff_mtr = p.mtr or par.mtr
        if mtr and eff_mtr != mtr:
            continue
        if supplier and (p.supplier or None) != supplier:
            continue
        if author and par.sostavitel != author:
            continue
        if not in_period(par.zagruzka):
            continue
        procs.append(p)
        parent_by_proc[p.id] = {
            "code": par.code, "title": par.title, "mtr": par.mtr, "srok": par.srok,
            "sostavitel": par.sostavitel, "dept": par.dept,
            "zagruzka": par.zagruzka, "created_by": par.created_by,
        }

    proc_ids = [p.id for p in procs] or [0]
    deliveries = db.query(Delivery).filter(Delivery.procedure_id.in_(proc_ids)).all()
    positions = db.query(ProcedurePosition).filter(ProcedurePosition.procedure_id.in_(proc_ids)).all()

    deliveries_by_proc = defaultdict(list)
    for d in deliveries:
        deliveries_by_proc[d.procedure_id].append(d)
    positions_by_proc = defaultdict(list)
    for pp in positions:
        positions_by_proc[pp.procedure_id].append(pp)
    delivery_proc = {d.id: d.procedure_id for d in deliveries}

    active = or_(Procedure.status_postavki.is_(None), Procedure.status_postavki != "Отменена")
    upds = (
        db.query(UpdPayment)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id, isouter=True)
        .join(Procedure, Delivery.procedure_id == Procedure.id, isouter=True)
        .filter(active)
        .all()
    )
    # R6: manual УПД (no delivery/procedure) can't be period-anchored → drop when a period is active
    if has_period:
        upds = [u for u in upds if u.delivery_id is not None]
    upds_by_proc = defaultdict(list)
    for u in upds:
        pid = delivery_proc.get(u.delivery_id)
        if pid is not None:
            upds_by_proc[pid].append(u)

    completed_proc_ids = set()
    for p in procs:
        if is_procedure_completed(p, upds_by_proc.get(p.id, [])):
            completed_proc_ids.add(p.id)

    aw_q = (
        db.query(ParentRequest)
        .filter(ParentRequest.status == "awaiting")
        .filter(~db.query(Tender).filter(Tender.parent_id == ParentRequest.id).exists())
    )
    awaiting_parents = []
    for par in aw_q.all():
        if mtr and par.mtr != mtr:
            continue
        if author and par.sostavitel != author:
            continue
        if not in_period(par.zagruzka):
            continue
        awaiting_parents.append(par)

    return SimpleNamespace(
        today=today, period_info=period_info, from_d=from_d, to_d=to_d, has_period=has_period,
        procs=procs, parent_by_proc=parent_by_proc,
        deliveries=deliveries, deliveries_by_proc=deliveries_by_proc,
        positions_by_proc=positions_by_proc,
        upds=upds, upds_by_proc=upds_by_proc, completed_proc_ids=completed_proc_ids,
        delivery_proc=delivery_proc, awaiting_parents=awaiting_parents,
    )


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
    "is_procedure_completed",
    "proc_sum",
    "_fmt_date",
    "report_time",
    "report_sums",
    "report_late",
    "report_people",
]
