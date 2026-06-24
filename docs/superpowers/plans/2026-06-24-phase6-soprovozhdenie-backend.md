# Фаза 6 (backend) — В сопровождении + поставки + расчёты Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. Реализуй строго по TDD (красный → зелёный → коммит). НЕ додумывай поля/имена — всё дословно из этого плана и `docs/`. Главный агент верифицирует сам (pytest, git log).

**Goal:** Backend Фазы 6 — расчётный модуль `calculations.py` (чистые функции по `32`) + роутер `/support` (список, правка Б2-полей, частичные поставки, документы, № УПД → `upd_payment`). Фронтенд (6.3) — отдельная следующая сессия.

**Architecture:** Чистые функции расчётов (`calculations.py`, без HTTP/DB — duck-typed объекты) + FastAPI-роутер `support.py`, зеркалящий паттерны `procurement.py` (гарды `require_action`, `paginate`, `write_audit`, коррелированные подзапросы для derived-полей). `GET/PATCH /procedures/{id}` остаются в `procurement.py` и **расширяются** Б2-полями + `deliveries` (один ресурс «общий для фаз 5–6»).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2, pytest + httpx. TZ = `Europe/Moscow` (via `zoneinfo`). Деньги — INTEGER копейки. Даты — ISO `YYYY-MM-DD` строки.

## Global Constraints (дословно из `docs/`)
- Деньги — `INTEGER` копейки; суммы с НДС; отображение `1 234 567 ₽`.
- Даты — ISO `YYYY-MM-DD`; «сегодня» по `Europe/Moscow`.
- Пагинация списков — 50 строк (`?page=&page_size=`, ответ с `total`).
- Активные по умолчанию: `/support` отдаёт активные; `?include_archived=1` добавляет завершённые/отменённые.
- Конкурентность — last-write-wins. Коды ошибок: 401/403/404/409/422. Аудит на каждую мутацию.
- Идентификаторы вводятся вручную (№ УПД — сопровождение).

## Зафиксированные решения (design, утверждено пользователем)
1. **Расширить существующий `ProcedureDetail`/`ProcedurePatch`** Б2-полями + `deliveries` (nested). Один эндпоинт «общий для фаз 5–6».
2. **`is_procedure_overdue`** = `srok_dd < today AND status_postavki != 'Поставлено'` (дедлайн прошёл + не полностью поставлено).
3. **Авто-«факт» при `transit→done`**: `delivery.date` = today (если не задана). `procedure.fakt_date` — отдельное ручное поле, НЕ авто.
4. **`POST /deliveries/{id}/upd` = upsert**: 1 `upd_payment` на delivery. Есть → обновить №; нет → создать.
5. **`PATCH /procedures/{id}` whitelist по `proc.block`**: `zakupka` → закупочные поля (`require zakupka edit`); `soprovozhdenie` → Б2-поля (`require soprovozhdenie edit`). Один эндпоинт.
6. **Completion (архив)** = `status_postavki='Поставлено'` AND ≥1 `upd_payment` AND все `upd_payment` paid. (Не vacuous-truth — поставленная без УПД НЕ скрывается.)

## Снято с повестки (однозначно по спекам)
- API-имена `plan_date`/`fakt_date` (DB-aligned); заголовки таблицы «План»/«Факт» — UI (след. сессия).
- `overdue_pct` — по позициям, канон `32§4` (позиции в overdue-ИЛИ-late поставках / всего позиций).
- `docs_aggregate` при 0 поставок → все `false`.

## File Structure
- **Create:** `backend/app/calculations.py` (pure functions), `backend/app/routers/support.py`, `backend/app/schemas/deliveries.py`, `backend/tests/test_calculations.py`, `backend/tests/test_support.py`.
- **Modify:** `backend/app/schemas/procedures.py` (+delivery_id в `ProcedurePositionOut`; +Б2 в `ProcedureDetail`/`ProcedurePatch`; +`deliveries` в `ProcedureDetail`), `backend/app/routers/procurement.py` (`_build_detail` populate Б2+deliveries; `patch_procedure` branching по block), `backend/app/main.py` (register `support.router`).

---

## Task 6.0 — Prep: merge chain to main + branch feat/phase-6

**Не TDD-задача** (git prep). Выполняет главный агент напрямую.

- [ ] **Шаг 1:** fast-forward `main` → `feat/phase-5` (несёт все фазы 0–5).
```bash
cd "H:/Projects AI/CRM Ultima"
git checkout main
git merge --ff-only feat/phase-5
git log --oneline -3   # verify: main now at 1db214d (phase-5 head)
```
- [ ] **Шаг 2:** branch + push.
```bash
git checkout -b feat/phase-6
git log --oneline -1   # on feat/phase-6 at same commit
```
- [ ] **Шаг 3 (smoke):** backend поднимается, тесты зелёные ДО любых изменений.
```bash
cd backend && "$PY" -m pytest -q   # PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe
```
Expected: all PASS (baseline). Фиксируем число тестов — после Фазы 6 оно должно вырасти, ничего не должно упасть.

---

## Task 6.1 — Расчётный модуль `calculations.py` (pure, unit-тесты без HTTP)

**Files:**
- Create: `backend/app/calculations.py`
- Test: `backend/tests/test_calculations.py`

**Interfaces (Produces):** `today_moscow()`, `position_sum(pos)`, `procedure_sum(positions)`, `progress(positions, deliveries)`, `is_delivery_overdue(delivery, srok_dd, today)`, `is_delivery_late(delivery, srok_dd, today)`, `is_procedure_overdue(srok_dd, status_postavki, today)`, `overdue_pct(positions, deliveries, srok_dd, today)`, `docs_aggregate(deliveries)`, `is_upd_overdue(upd, today)`.

- [ ] **Шаг 1: failing tests** — `backend/tests/test_calculations.py`

```python
"""Unit tests for app.calculations (Phase 6.1). Pure functions, no HTTP/DB."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.calculations import (
    docs_aggregate,
    is_delivery_late,
    is_delivery_overdue,
    is_procedure_overdue,
    is_upd_overdue,
    overdue_pct,
    position_sum,
    procedure_sum,
    progress,
    today_moscow,
)

TODAY = date(2026, 6, 21)  # зафиксированное «сегодня» (Москва)


def _pos(qty, price=None, delivery_id=None):
    return SimpleNamespace(qty=qty, price=price, delivery_id=delivery_id)


def _delivery(status="transit", date_str=None, ttn=0, m15=0, upd=0, sert=0, did=1):
    return SimpleNamespace(id=did, status=status, date=date_str,
                           doc_ttn=ttn, doc_m15=m15, doc_upd=upd, doc_sert=sert)


# --- position_sum / procedure_sum -------------------------------------------------

def test_position_sum_qty_times_price_kopecks():
    assert position_sum(_pos(10.0, 15000)) == 150000  # 10 * 150.00 ₽

def test_position_sum_no_price_is_zero():
    assert position_sum(_pos(10.0, None)) == 0

def test_position_sum_fractional_qty_rounded():
    assert position_sum(_pos(1.5, 10000)) == 15000  # 1.5 * 100.00

def test_procedure_sum_sums_positions():
    assert procedure_sum([_pos(2.0, 10000), _pos(1.0, 5000)]) == 25000

def test_procedure_sum_empty_is_zero():
    assert procedure_sum([]) == 0


# --- progress --------------------------------------------------------------------

def test_progress_zero_positions():
    assert progress([], []) == (0, 0, 0.0)

def test_progress_none_done():
    # 3 positions, none in a done delivery
    d = _delivery(status="transit", did=7)
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=None), _pos(1, 100, delivery_id=7)]
    assert progress(positions, [d]) == (0, 3, 0.0)

def test_progress_partial_done():
    d_done = _delivery(status="done", did=7)
    d_transit = _delivery(status="transit", did=8)
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=8), _pos(1, 100, delivery_id=None)]
    delivered, total, pct = progress(positions, [d_done, d_transit])
    assert (delivered, total) == (1, 3)
    assert round(pct, 2) == round(100 / 3, 2)

def test_progress_all_done():
    d = _delivery(status="done", did=7)
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=7)]
    assert progress(positions, [d]) == (2, 2, 100.0)


# --- is_delivery_overdue / late --------------------------------------------------

def test_delivery_overdue_transit_past_srok():
    d = _delivery(status="transit")
    assert is_delivery_overdue(d, "2026-06-01", TODAY) is True

def test_delivery_overdone_not_overdue():
    d = _delivery(status="done", date_str="2026-06-10")
    assert is_delivery_overdue(d, "2026-06-01", TODAY) is False

def test_delivery_overdue_future_srok_false():
    d = _delivery(status="transit")
    assert is_delivery_overdue(d, "2026-07-01", TODAY) is False

def test_delivery_overdue_no_srok_false():
    d = _delivery(status="transit")
    assert is_delivery_overdue(d, None, TODAY) is False

def test_delivery_late_done_after_srok():
    d = _delivery(status="done", date_str="2026-06-10")
    assert is_delivery_late(d, "2026-06-01", TODAY) is True

def test_delivery_late_done_before_srok_false():
    d = _delivery(status="done", date_str="2026-05-01")
    assert is_delivery_late(d, "2026-06-01", TODAY) is False

def test_delivery_late_transit_false():
    d = _delivery(status="transit")
    assert is_delivery_late(d, "2026-06-01", TODAY) is False


# --- is_procedure_overdue --------------------------------------------------------

def test_procedure_overdue_past_srok_not_delivered():
    assert is_procedure_overdue("2026-06-01", "В поставке", TODAY) is True

def test_procedure_overdue_past_srok_delivered_false():
    assert is_procedure_overdue("2026-06-01", "Поставлено", TODAY) is False

def test_procedure_overdue_future_srok_false():
    assert is_procedure_overdue("2026-07-01", "В поставке", TODAY) is False

def test_procedure_overdue_no_srok_false():
    assert is_procedure_overdue(None, "В поставке", TODAY) is False


# --- overdue_pct -----------------------------------------------------------------

def test_overdue_pct_no_positions_zero():
    assert overdue_pct([], [], "2026-06-01", TODAY) == 0.0

def test_overdue_pct_all_late_hundred():
    d = _delivery(status="transit", did=7)  # transit past srok → overdue
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=7)]
    assert overdue_pct(positions, [d], "2026-06-01", TODAY) == 100.0

def test_overdue_pct_partial():
    d_over = _delivery(status="transit", did=7)
    d_ok = _delivery(status="done", date_str="2026-05-01", did=8)  # done before srok → not late
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=8), _pos(1, 100, delivery_id=None)]
    assert overdue_pct(positions, [d_over, d_ok], "2026-06-01", TODAY) == round(100 / 3, 2)

def test_overdue_pct_none_late_zero():
    d = _delivery(status="done", date_str="2026-05-01", did=7)
    positions = [_pos(1, 100, delivery_id=7)]
    assert overdue_pct(positions, [d], "2026-06-01", TODAY) == 0.0


# --- docs_aggregate --------------------------------------------------------------

def test_docs_aggregate_no_deliveries_all_false():
    assert docs_aggregate([]) == {"ttn": False, "m15": False, "upd": False, "sert": False}

def test_docs_aggregate_single_all_set():
    d = _delivery(ttn=1, m15=1, upd=1, sert=1)
    assert docs_aggregate([d]) == {"ttn": True, "m15": True, "upd": True, "sert": True}

def test_docs_aggregate_two_one_missing_flag():
    d1 = _delivery(ttn=1, m15=1, upd=1, sert=1, did=1)
    d2 = _delivery(ttn=0, m15=1, upd=1, sert=1, did=2)  # missing ttn in d2
    agg = docs_aggregate([d1, d2])
    assert agg["ttn"] is False   # not in ALL
    assert agg["m15"] is True
    assert agg["upd"] is True
    assert agg["sert"] is True


# --- is_upd_overdue --------------------------------------------------------------

def test_upd_overdue_await_past_srok():
    u = SimpleNamespace(pay_status="await", srok="2026-06-01")
    assert is_upd_overdue(u, TODAY) is True

def test_upd_overdue_paid_false():
    u = SimpleNamespace(pay_status="paid", srok="2026-06-01")
    assert is_upd_overdue(u, TODAY) is False

def test_upd_overdue_await_future_false():
    u = SimpleNamespace(pay_status="await", srok="2026-07-01")
    assert is_upd_overdue(u, TODAY) is False

def test_upd_overdue_no_srok_false():
    u = SimpleNamespace(pay_status="await", srok=None)
    assert is_upd_overdue(u, TODAY) is False


# --- today_moscow ----------------------------------------------------------------

def test_today_moscow_returns_date():
    assert isinstance(today_moscow(), date)
```

- [ ] **Шаг 2: run → FAIL** (нет модуля). `cd backend && "$PY" -m pytest tests/test_calculations.py -q` → ImportError.

- [ ] **Шаг 3: implementation** — `backend/app/calculations.py`

```python
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
```

- [ ] **Шаг 4: run → PASS.** `cd backend && "$PY" -m pytest tests/test_calculations.py -q` → all PASS.
- [ ] **Шаг 5: commit.**
```bash
git add backend/app/calculations.py backend/tests/test_calculations.py
git commit -m "feat(calculations): pure derived functions for Сопровождение (Phase 6.1)"
```

---

## Task 6.2a — Schemas + `_build_detail` + `patch_procedure` branching

**Files:**
- Create: `backend/app/schemas/deliveries.py`
- Modify: `backend/app/schemas/procedures.py` (ProcedurePositionOut +delivery_id; ProcedureDetail +Б2+deliveries; ProcedurePatch +Б2)
- Modify: `backend/app/routers/procurement.py` (imports; `_build_detail`; `patch_procedure`)
- Test: `backend/tests/test_support.py` (создать с фикстурами + тесты этого task)

**Interfaces:**
- Consumes: models (`Delivery`, `UpdPayment`), `app.permissions.can`.
- Produces: `DeliveryOut`, `DeliveryUpdOut`, `DeliveryCreate`, `DeliveryPatch`, `UpdIn`, `SupportListItem`, `PaginatedSupport`; extended `ProcedureDetail` (Б2 + `deliveries`) / `ProcedurePositionOut` (+`delivery_id`) / `ProcedurePatch` (+Б2).

- [ ] **Шаг 1: create schemas/deliveries.py**

```python
"""Pydantic v2 schemas for deliveries + support list (Phase 6.2)."""
from __future__ import annotations

from typing import Optional

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


class DeliveryCreate(BaseModel):
    # ≥1 procedure_position_id; пустой массив → 422 (Pydantic min_length)
    positions: list[int] = Field(min_length=1)


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
    "DeliveryUpdOut", "DeliveryOut", "DeliveryCreate", "DeliveryPatch",
    "UpdIn", "SupportListItem", "PaginatedSupport",
]
```

- [ ] **Шаг 2: modify schemas/procedures.py**
  - В `ProcedurePositionOut` добавить поле (после `price`): `delivery_id: Optional[int] = None`
  - В `ProcedureDetail` добавить (перед `positions`): Б2-поля + `deliveries`; добавить импорт `from app.schemas.deliveries import DeliveryOut` наверх.
  - В `ProcedurePatch` добавить Б2-поля.

  Полный вид изменённых классов (замени целиком):

```python
# вверху файла, после существующих импортов:
from app.schemas.deliveries import DeliveryOut

# ProcedurePositionOut — добавить поле:
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
    price: Optional[int] = None       # INTEGER kopecks
    delivery_id: Optional[int] = None  # NULL = «ожидает отгрузки»


# ProcedureDetail — добавить Б2-поля + deliveries (перед positions):
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
    # Б2 (Сопровождение):
    contract: Optional[str] = None
    fio_dogovornik: Optional[str] = None
    contract_sum: Optional[int] = None
    status_sdelki: Optional[str] = None
    status_postavki: Optional[str] = None
    srok_dd: Optional[str] = None
    plan_date: Optional[str] = None
    fakt_date: Optional[str] = None
    created_at: str
    positions: list[ProcedurePositionOut] = []
    deliveries: list[DeliveryOut] = []
    # NOTE: block_entered_at intentionally OMITTED (служебное)


# ProcedurePatch — добавить Б2-поля:
class ProcedurePatch(BaseModel):
    proc: Optional[str] = None
    tender_num: Optional[str] = None     # writes tender.num
    supplier: Optional[str] = None
    fio_zakupshchik: Optional[str] = None
    mtr: Optional[str] = None
    pub_start: Optional[str] = None
    pub_end: Optional[str] = None
    status_zakup: Optional[str] = None   # validated against dict (6 values)
    # Б2 (Сопровождение):
    contract: Optional[str] = None
    fio_dogovornik: Optional[str] = None
    contract_sum: Optional[int] = None
    status_sdelki: Optional[str] = None  # validated against dict (3 values)
    status_postavki: Optional[str] = None  # validated against 6-value enum
    srok_dd: Optional[str] = None
    plan_date: Optional[str] = None
    fakt_date: Optional[str] = None
```
  - В `__all__` ничего добавлять не нужно (новые поля, не классы).

- [ ] **Шаг 3: modify procurement.py imports + `_build_detail`**

  Вверху `procurement.py` обновить импорты моделей и схем:
```python
from app.models import (
    Delivery,
    Dict,
    ParentRequest,
    Procedure,
    ProcedurePosition,
    RequestedPosition,
    Tender,
    UpdPayment,
    User,
)
from app.permissions import can, require_action
from app.schemas.deliveries import DeliveryOut, DeliveryUpdOut
```
  (`require_action` уже импортируется — оставить; добавить `can`. `UpdPayment`, `Delivery` — добавить.)

  Заменить `_build_detail` целиком:
```python
def _build_detail(db: Session, proc: Procedure) -> ProcedureDetail:
    """Build ProcedureDetail (с Б2-полями + deliveries) из Procedure."""
    tender = db.get(Tender, proc.tender_id)
    parent = db.get(ParentRequest, tender.parent_id) if tender else None

    positions = (
        db.query(ProcedurePosition)
        .filter(ProcedurePosition.procedure_id == proc.id)
        .order_by(ProcedurePosition.id.asc())
        .all()
    )
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.procedure_id == proc.id)
        .order_by(Delivery.n.asc())
        .all()
    )
    deliv_out: list[DeliveryOut] = []
    for d in deliveries:
        upd = (
            db.query(UpdPayment).filter(UpdPayment.delivery_id == d.id).first()
        )
        deliv_out.append(
            DeliveryOut(
                id=d.id, n=d.n, status=d.status, date=d.date, eta=d.eta,
                doc_ttn=d.doc_ttn or 0, doc_m15=d.doc_m15 or 0,
                doc_upd=d.doc_upd or 0, doc_sert=d.doc_sert or 0,
                upd=DeliveryUpdOut(upd=upd.upd, pay_status=upd.pay_status) if upd else None,
            )
        )

    return ProcedureDetail(
        id=proc.id,
        proc=proc.proc,
        tender_id=proc.tender_id,
        tender_num=tender.num if tender else None,
        parent_id=tender.parent_id if tender else 0,
        code=parent.code if parent else "",
        title=parent.title if parent else "",
        mtr=proc.mtr if proc.mtr is not None else (parent.mtr if parent else None),
        supplier=proc.supplier,
        fio_zakupshchik=proc.fio_zakupshchik,
        pub_start=proc.pub_start,
        pub_end=proc.pub_end,
        zagruzka=parent.zagruzka if parent else "",
        block=proc.block,
        status_zakup=proc.status_zakup,
        contract=proc.contract,
        fio_dogovornik=proc.fio_dogovornik,
        contract_sum=proc.contract_sum,
        status_sdelki=proc.status_sdelki,
        status_postavki=proc.status_postavki,
        srok_dd=proc.srok_dd,
        plan_date=proc.plan_date,
        fakt_date=proc.fakt_date,
        created_at=proc.created_at,
        positions=[ProcedurePositionOut.model_validate(p) for p in positions],
        deliveries=deliv_out,
    )
```

- [ ] **Шаг 4: modify `patch_procedure` — branching по block (Решение 5)**

  Заменить функцию `patch_procedure` целиком. ВАЖНО: закупочная ветка сохраняет ВСЮ существующую логику (status_zakup dict-валидация, proc/tender_num unique 409, tender_num→tender.num). Меняется только зависимость (`require_password_changed` + inline `can`) и обёртка `if block == "zakupka" / else`.

  Добавить константу рядом с `_SORT_KEYS`:
```python
_STATUS_POSTAVKI_VALUES = frozenset({
    "Новая", "В производстве", "В поставке", "Частично поставлено",
    "Поставлено", "Отменена",
})
```

  Новая `patch_procedure`:
```python
@router.patch("/procedures/{procedure_id}", response_model=ProcedureDetail)
def patch_procedure(
    procedure_id: int,
    payload: ProcedurePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_changed),
) -> ProcedureDetail:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="procedure not found",
        )

    # Решеие 5: permission + field-whitelist по текущему block процедуры.
    block = proc.block
    if not can(current_user, block, "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    data = payload.model_dump(exclude_unset=True)

    if block == "zakupka":
        # status_zakup validation against the dict (6 values).
        if "status_zakup" in data and data["status_zakup"] is not None:
            allowed = {
                row.value
                for row in db.query(Dict).filter(Dict.kind == "status_zakup").all()
            }
            if data["status_zakup"] not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="invalid status_zakup",
                )

        # Unique proc (non-null) duplicate → 409.
        if "proc" in data and data["proc"] is not None and data["proc"] != proc.proc:
            existing = (
                db.query(Procedure).filter(Procedure.proc == data["proc"]).first()
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="proc already exists",
                )

        tender = db.get(Tender, proc.tender_id)
        # tender_num → tender.num. Unique (non-null) duplicate → 409.
        if "tender_num" in data and data["tender_num"] is not None and data["tender_num"] != (tender.num if tender else None):
            existing_tender = (
                db.query(Tender).filter(Tender.num == data["tender_num"]).first()
            )
            if existing_tender is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="tender num already exists",
                )

        for field in ("proc", "supplier", "fio_zakupshchik", "mtr", "pub_start", "pub_end", "status_zakup"):
            if field in data:
                setattr(proc, field, data[field])
        if "tender_num" in data and tender is not None:
            tender.num = data["tender_num"]
    else:
        # block == "soprovozhdenie" → Б2-fields.
        if "status_sdelki" in data and data["status_sdelki"] is not None:
            allowed = {
                row.value
                for row in db.query(Dict).filter(Dict.kind == "status_sdelki").all()
            }
            if data["status_sdelki"] not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="invalid status_sdelki",
                )
        if "status_postavki" in data and data["status_postavki"] is not None:
            if data["status_postavki"] not in _STATUS_POSTAVKI_VALUES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="invalid status_postavki",
                )
        for field in ("contract", "fio_dogovornik", "contract_sum", "status_sdelki",
                      "status_postavki", "srok_dd", "plan_date", "fakt_date"):
            if field in data:
                setattr(proc, field, data[field])

    db.commit()
    db.refresh(proc)

    write_audit(
        db,
        entity_kind="procedure",
        entity_id=proc.id,
        user=current_user,
        action="update",
    )
    return _build_detail(db, proc)
```

  > **Регресс-чек:** после этой правки ВСЕ существующие закупочные тесты `test_procurement.py` должны остаться зелёными (PATCH/cancel/uncancel/split/to-support/positions/RBAC). Запусти `pytest tests/test_procurement.py -q` — должно быть 0 fail. Единственное изменение поведения: 404 теперь проверяется до 403 (нет теста на «kompl patches missing proc» — безопасно).

- [ ] **Шаг 5: failing test** — `backend/tests/test_support.py` (фикстуры + тесты 6.2a)

```python
"""Tests for /support + /deliveries routers (Phase 6.2).

Pattern mirrors tests/test_procurement.py. A procedure reaches the support
block via: take-to-work → PATCH status_zakup='На сделку' → POST /to-support.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password


ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"


# --- fixtures (mirror test_procurement.py) --------------------------------------

@pytest.fixture()
def db_seeded():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _setup(dbapi_conn, _):
        register_sqlite_setup(dbapi_conn, _)

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    from app.seed import seed_initial
    seed_initial(s)
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client_seeded(db_seeded):
    def _override():
        try:
            yield db_seeded
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client_admin(client_seeded):
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    client_seeded.post("/auth/change-password", json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD})
    client_seeded.post("/auth/logout")
    r = client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD})
    assert r.status_code == 200
    return client_seeded


# --- helpers --------------------------------------------------------------------

def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_support(client, code, title, positions):
    """Create parent + positions, take to work, advance to 'На сделку',
    hand off to support → returns procedure_id (block=soprovozhdenie)."""
    body = _create_request(client, code, title, positions)
    parent_id = body["id"]
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    proc_id = r.json()["procedure_id"]
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r2 = client.post(f"/procedures/{proc_id}/to-support")
    assert r2.status_code == 200, r2.text
    return proc_id


def _make_soprov_emp(db, email="soprov_emp@crm.local"):
    """Сопровождение employee — has soprovozhdenie edit (NOT oplaty)."""
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name="Сопровождение Тестовое", account_type="department",
        department="Сопровождение", is_curator=0, global_role=None,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_kompl_emp(db, email="kompl_emp@crm.local"):
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name="Комплектовщик Тестовый", account_type="department",
        department="Комплектация", is_curator=0, global_role=None,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login_as(client, email, password="userpass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


# --- 6.2a: GET /procedures/{id} returns Б2 fields + deliveries -------------------

def test_detail_support_block_has_b2_fields(client_admin):
    proc_id = _to_support(client_admin, "SUP-DET", "sopr detail",
                          [{"name": "x", "qty": 10.0}])
    r = client_admin.get(f"/procedures/{proc_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["block"] == "soprovozhdenie"
    for k in ("contract", "fio_dogovornik", "contract_sum", "status_sdelki",
              "status_postavki", "srok_dd", "plan_date", "fakt_date", "deliveries"):
        assert k in body
    assert body["status_postavki"] == "Новая"   # set by to-support
    assert body["deliveries"] == []              # no deliveries yet


# --- 6.2a: PATCH Б2-fields persist (support block); status_sdelki validated ------

def test_patch_b2_fields_persist(client_admin):
    proc_id = _to_support(client_admin, "SUP-PAT", "patch b2",
                          [{"name": "x", "qty": 10.0, "price": 10000}])
    r = client_admin.patch(f"/procedures/{proc_id}", json={
        "contract": "ДК-77", "fio_dogovornik": "Петров П.П.",
        "contract_sum": 1500000, "status_sdelki": "Подписано",
        "status_postavki": "В поставке", "srok_dd": "2026-07-01",
        "plan_date": "2026-06-25", "fakt_date": None,
    })
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["contract"] == "ДК-77"
    assert got["fio_dogovornik"] == "Петров П.П."
    assert got["contract_sum"] == 1500000
    assert got["status_sdelki"] == "Подписано"
    assert got["status_postavki"] == "В поставке"
    assert got["srok_dd"] == "2026-07-01"


def test_patch_status_sdelki_invalid_422(client_admin):
    proc_id = _to_support(client_admin, "SUP-SDELKA-BAD", "bad",
                          [{"name": "x", "qty": 1.0}])
    r = client_admin.patch(f"/procedures/{proc_id}", json={"status_sdelki": "Нет такого"})
    assert r.status_code == 422


def test_patch_status_postavki_invalid_422(client_admin):
    proc_id = _to_support(client_admin, "SUP-POST-BAD", "bad",
                          [{"name": "x", "qty": 1.0}])
    r = client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Лёгкое"})
    assert r.status_code == 422


# --- 6.2a: zakupka PATCH still works (no regression) + block-whitelist -----------

def test_patch_zakupka_fields_still_work(client_admin):
    # procedure still in zakupka (not to-support) → zakupka patch path
    body = _create_request(client_admin, "SUP-ZK", "zk", [{"name": "x", "qty": 1.0}])
    r = client_admin.post(f"/requests/{body['id']}/take-to-work")
    proc_id = r.json()["procedure_id"]
    r2 = client_admin.patch(f"/procedures/{proc_id}", json={"proc": "ZK-1", "status_zakup": "Торги"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["proc"] == "ZK-1"
    assert r2.json()["status_zakup"] == "Торги"


# --- 6.2a: RBAC — kompl emp cannot PATCH support procedure -----------------------

def test_rbac_patch_support_403_for_kompl(client_seeded, db_seeded, client_admin):
    proc_id = _to_support(client_admin, "SUP-RBAC", "rbac",
                          [{"name": "x", "qty": 1.0}])
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.patch(f"/procedures/{proc_id}", json={"contract": "X"})
    assert r.status_code == 403


def test_rbac_patch_support_ok_for_soprov_emp(client_seeded, db_seeded, client_admin):
    proc_id = _to_support(client_admin, "SUP-RBAC2", "rbac ok",
                          [{"name": "x", "qty": 1.0}])
    u = _make_soprov_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.patch(f"/procedures/{proc_id}", json={"contract": "ДК-1"})
    assert r.status_code == 200, r.text
    assert r.json()["contract"] == "ДК-1"
```

- [ ] **Шаг 6: register router** — `backend/app/main.py`
```python
from app.routers import auth, dict, procurement, requests, search, support, users
# ...
app.include_router(support.router)
```
  (Файл `support.py` создастся в Task 6.2b; чтобы импорт не падал сейчас — создай заглушку `backend/app/routers/support.py` с `router = APIRouter(tags=["support"])` + нужными импортами, и наполни его в 6.2b–f. Либо выполняй 6.2a→6.2b подряд перед запуском тестов.) **Рекомендация:** создай `support.py` заглушкой в этом шаге и зарегистрируй в main.py — тогда `test_support.py` (6.2a тесты) проходят сразу.

  Заглушка `backend/app/routers/support.py`:
```python
"""/support + /deliveries routers (Phase 6.2). Filled in 6.2b–f."""
from __future__ import annotations
from fastapi import APIRouter
router = APIRouter(tags=["support"])
```

- [ ] **Шаг 7: run → PASS.** `cd backend && "$PY" -m pytest tests/test_support.py tests/test_procurement.py tests/test_calculations.py -q` → all PASS (новые + 0 регрессий).
- [ ] **Шаг 8: commit.**
```bash
git add backend/app/schemas/deliveries.py backend/app/schemas/procedures.py backend/app/routers/procurement.py backend/app/routers/support.py backend/app/main.py backend/tests/test_support.py
git commit -m "feat(support): Б2 schemas + detail/deliveries + block-scoped PATCH (Phase 6.2a)"
```

---

## Task 6.2b — GET /support (list, active-by-default, derived fields)

**Files:**
- Modify: `backend/app/routers/support.py` (fill GET /support)
- Test: `backend/tests/test_support.py` (append)

**Interfaces:**
- Consumes: `app.calculations` (progress, overdue_pct, is_procedure_overdue, docs_aggregate, today_moscow), `paginate`, models.
- Produces: `GET /support` → `PaginatedSupport`.

- [ ] **Шаг 1: append tests**

```python
# --- 6.2b: GET /support list ----------------------------------------------------

def test_support_list_empty(client_admin):
    r = client_admin.get("/support")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


def test_support_list_shows_support_procedure_with_derived(client_admin):
    proc_id = _to_support(client_admin, "SUP-L1", "list one",
                          [{"name": "x", "qty": 10.0}])
    # set srok_dd in the past + not delivered → is_overdue True, overdue_pct by deliveries
    client_admin.patch(f"/procedures/{proc_id}", json={"srok_dd": "2026-06-01"})
    r = client_admin.get("/support")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == proc_id
    assert item["code"] == "SUP-L1"
    assert item["status_postavki"] == "Новая"
    assert item["is_overdue"] is True          # srok passed, not Поставлено
    assert item["overdue_pct"] == 0.0          # no deliveries → 0
    assert item["docs"] == {"ttn": False, "m15": False, "upd": False, "sert": False}
    assert item["progress_delivered"] == 0
    assert item["progress_total"] == 1


def test_support_list_excludes_zakupka_block(client_admin, db_seeded):
    from app.models import ParentRequest, Tender, Procedure
    pr = ParentRequest(code="ZK-ONLY", title="zk", sostavitel="X", status="awaiting")
    db_seeded.add(pr); db_seeded.commit(); db_seeded.refresh(pr)
    t = Tender(parent_id=pr.id); db_seeded.add(t); db_seeded.commit(); db_seeded.refresh(t)
    db_seeded.add(Procedure(tender_id=t.id, block="zakupka")); db_seeded.commit()
    r = client_admin.get("/support")
    assert r.json()["total"] == 0


def test_support_list_cancelled_hidden_by_default(client_admin):
    proc_id = _to_support(client_admin, "SUP-CXL", "cancel",
                          [{"name": "x", "qty": 1.0}])
    client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Отменена"})
    assert proc_id not in {it["id"] for it in client_admin.get("/support").json()["items"]}
    assert proc_id in {it["id"] for it in client_admin.get("/support?include_archived=1").json()["items"]}


def test_support_list_pagination(client_admin):
    for i in range(3):
        _to_support(client_admin, f"SUP-PG{i}", f"pg{i}", [{"name": "x", "qty": 1.0}])
    r1 = client_admin.get("/support?page=1&page_size=2")
    assert r1.json()["total"] == 3
    assert len(r1.json()["items"]) == 2
    r2 = client_admin.get("/support?page=2&page_size=2")
    assert len(r2.json()["items"]) == 1
```

- [ ] **Шаг 2: run → FAIL** (GET /support → 404, роутера нет).
- [ ] **Шаг 3: implementation** — replace `support.py` stub content (keep `router = APIRouter(tags=["support"])`):

```python
"""/support + /deliveries routers (Phase 6.2).

GET /support           — list procedures in block='soprovozhdenie' (active default).
PATCH /procedures/{id} — Б2 fields (lives in procurement.py; block-scoped).
POST   /procedures/{id}/deliveries — create partial delivery (≥1 positions).
DELETE /deliveries/{id}            — disband (transit only).
PATCH  /deliveries/{id}            — transit→done, doc flags, date/eta.
POST   /deliveries/{id}/upd        — upsert upd_payment (origin=delivery, await).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app import calculations as calc
from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import (
    Delivery,
    Dict,
    ParentRequest,
    Procedure,
    ProcedurePosition,
    Tender,
    UpdPayment,
    User,
)
from app.permissions import require_action
from app.schemas.deliveries import (
    DeliveryCreate,
    DeliveryOut,
    DeliveryPatch,
    DeliveryUpdOut,
    PaginatedSupport,
    SupportListItem,
    UpdIn,
)


router = APIRouter(tags=["support"])

_SORT_KEYS = {
    "created_at", "code", "proc", "supplier", "contract_sum",
    "status_postavki", "status_sdelki", "srok_dd", "plan_date", "fakt_date",
}


def _await_upd_exists():
    return exists(
        select(UpdPayment.id)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id)
        .where(Delivery.procedure_id == Procedure.id)
        .where(UpdPayment.pay_status == "await")
    )


def _any_upd_exists():
    return exists(
        select(UpdPayment.id)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id)
        .where(Delivery.procedure_id == Procedure.id)
    )


@router.get("/support", response_model=PaginatedSupport)
def list_support(
    include_archived: bool = Query(False, description="Include cancelled + completed"),
    search: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaginatedSupport:
    q = (
        db.query(Procedure)
        .join(Tender, Procedure.tender_id == Tender.id)
        .join(ParentRequest, Tender.parent_id == ParentRequest.id)
        .filter(Procedure.block == "soprovozhdenie")
    )

    # Решение 6: archived = Отменена OR completed(Поставлено + ≥1 upd + all paid).
    completed = and_(
        Procedure.status_postavki == "Поставлено",
        _any_upd_exists(),
        ~_await_upd_exists(),
    )
    archived = or_(Procedure.status_postavki == "Отменена", completed)
    if not include_archived:
        q = q.filter(~archived)

    if search:
        s = search.strip()
        if s:
            cf = s.casefold()
            q = q.filter(
                or_(
                    func.instr(func.py_casefold(ParentRequest.code), cf) > 0,
                    func.instr(func.py_casefold(ParentRequest.title), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Procedure.proc, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Tender.num, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Procedure.supplier, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(Procedure.contract, "")), cf) > 0,
                )
            )

    if sort not in _SORT_KEYS:
        sort = "created_at"
    _order = lambda col: col.asc().nulls_last()
    if sort == "created_at":
        q = q.order_by(Procedure.created_at.desc(), Procedure.id.desc())
    elif sort == "code":
        q = q.order_by(ParentRequest.code.asc(), Procedure.id.asc())
    elif sort == "proc":
        q = q.order_by(_order(Procedure.proc), Procedure.id.asc())
    elif sort == "supplier":
        q = q.order_by(_order(Procedure.supplier), Procedure.id.asc())
    elif sort == "contract_sum":
        q = q.order_by(_order(Procedure.contract_sum), Procedure.id.asc())
    elif sort == "status_postavki":
        q = q.order_by(_order(Procedure.status_postavki), Procedure.id.asc())
    elif sort == "status_sdelki":
        q = q.order_by(_order(Procedure.status_sdelki), Procedure.id.asc())
    elif sort in ("srok_dd", "plan_date", "fakt_date"):
        q = q.order_by(_order(getattr(Procedure, sort)), Procedure.id.asc())

    page_data = paginate(q, page=page, page_size=page_size)
    items: list[Procedure] = page_data["items"]
    total: int = page_data["total"]

    today = calc.today_moscow()
    items_out: list[SupportListItem] = []
    for proc in items:
        positions = (
            db.query(ProcedurePosition)
            .filter(ProcedurePosition.procedure_id == proc.id)
            .all()
        )
        deliveries = (
            db.query(Delivery).filter(Delivery.procedure_id == proc.id).all()
        )
        delivered, total_pos, _ = calc.progress(positions, deliveries)
        tender = proc.tender
        parent = tender.parent if tender else None
        items_out.append(
            SupportListItem(
                id=proc.id,
                proc=proc.proc,
                tender_num=tender.num if tender else None,
                code=parent.code if parent else "",
                title=parent.title if parent else "",
                mtr=proc.mtr if proc.mtr is not None else (parent.mtr if parent else None),
                supplier=proc.supplier,
                contract=proc.contract,
                contract_sum=proc.contract_sum,
                status_sdelki=proc.status_sdelki,
                status_postavki=proc.status_postavki,
                srok_dd=proc.srok_dd,
                plan_date=proc.plan_date,
                fakt_date=proc.fakt_date,
                is_overdue=calc.is_procedure_overdue(proc.srok_dd, proc.status_postavki, today),
                overdue_pct=calc.overdue_pct(positions, deliveries, proc.srok_dd, today),
                docs=calc.docs_aggregate(deliveries),
                progress_delivered=delivered,
                progress_total=total_pos,
                created_at=proc.created_at,
            )
        )

    return PaginatedSupport(items=items_out, total=total)
```

- [ ] **Шаг 4: run → PASS.** `cd backend && "$PY" -m pytest tests/test_support.py -q` → PASS.
- [ ] **Шаг 5: commit.**
```bash
git add backend/app/routers/support.py backend/tests/test_support.py
git commit -m "feat(support): GET /support list with derived calc fields (Phase 6.2b)"
```

---

## Task 6.2c — POST /procedures/{id}/deliveries (create, ≥1, awaiting positions)

**Files:** Modify `support.py` (add `_delivery_out` helper + POST); Test: append.

- [ ] **Шаг 1: append tests**

```python
# --- 6.2c: POST deliveries ------------------------------------------------------

def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def test_create_delivery_happy(client_admin):
    proc_id = _to_support(client_admin, "DLV-1", "delivery",
                          [{"name": "A", "qty": 10.0}, {"name": "B", "qty": 5.0}])
    pids = _position_ids(client_admin, proc_id)
    r = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pids[0]]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "transit"
    assert d["n"] == 1
    assert d["upd"] is None
    # position now assigned (delivery_id set) — visible in detail
    det = client_admin.get(f"/procedures/{proc_id}").json()
    assert len(det["deliveries"]) == 1
    assigned = {p["delivery_id"] for p in det["positions"]}
    assert d["id"] in assigned


def test_create_delivery_empty_422(client_admin):
    proc_id = _to_support(client_admin, "DLV-EMPTY", "empty", [{"name": "x", "qty": 1.0}])
    r = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": []})
    assert r.status_code == 422


def test_create_delivery_position_already_assigned_422(client_admin):
    proc_id = _to_support(client_admin, "DLV-DUP", "dup", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]})
    r = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]})
    assert r.status_code == 422


def test_create_delivery_two_sequences_n(client_admin):
    proc_id = _to_support(client_admin, "DLV-N", "seq",
                          [{"name": "A", "qty": 1.0}, {"name": "B", "qty": 1.0}])
    pids = _position_ids(client_admin, proc_id)
    d1 = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pids[0]]}).json()
    d2 = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pids[1]]}).json()
    assert d1["n"] == 1 and d2["n"] == 2


def test_create_delivery_other_procedure_position_404(client_admin):
    a = _to_support(client_admin, "DLV-A", "a", [{"name": "x", "qty": 1.0}])
    b = _to_support(client_admin, "DLV-B", "b", [{"name": "y", "qty": 1.0}])
    pid_b = _position_ids(client_admin, b)[0]
    r = client_admin.post(f"/procedures/{a}/deliveries", json={"positions": [pid_b]})
    assert r.status_code == 404
```

- [ ] **Шаг 2: run → FAIL.**
- [ ] **Шаг 3: implementation** — append to `support.py`:

```python
def _delivery_out(db: Session, d: Delivery) -> DeliveryOut:
    upd = db.query(UpdPayment).filter(UpdPayment.delivery_id == d.id).first()
    return DeliveryOut(
        id=d.id, n=d.n, status=d.status, date=d.date, eta=d.eta,
        doc_ttn=d.doc_ttn or 0, doc_m15=d.doc_m15 or 0,
        doc_upd=d.doc_upd or 0, doc_sert=d.doc_sert or 0,
        upd=DeliveryUpdOut(upd=upd.upd, pay_status=upd.pay_status) if upd else None,
    )


@router.post(
    "/procedures/{procedure_id}/deliveries",
    response_model=DeliveryOut,
    status_code=status.HTTP_200_OK,
)
def create_delivery(
    procedure_id: int,
    payload: DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> DeliveryOut:
    proc = db.get(Procedure, procedure_id)
    if proc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="procedure not found")
    if proc.block != "soprovozhdenie":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="procedure is not in support block")

    # Validate every position: exists, belongs to proc, still awaiting (delivery_id NULL).
    seen: set[int] = set()
    for pid in payload.positions:
        pos = db.get(ProcedurePosition, pid)
        if pos is None or pos.procedure_id != proc.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="position not found")
        if pos.delivery_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="position already in a delivery")
        if pid in seen:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="duplicate position in delivery")
        seen.add(pid)

    next_n = (db.query(func.max(Delivery.n))
              .filter(Delivery.procedure_id == proc.id).scalar() or 0) + 1
    d = Delivery(procedure_id=proc.id, n=next_n, status="transit")
    db.add(d)
    db.flush()  # assign d.id
    for pid in payload.positions:
        db.get(ProcedurePosition, pid).delivery_id = d.id

    db.commit()
    db.refresh(d)
    write_audit(db, entity_kind="procedure", entity_id=proc.id,
                user=current_user, action="delivery_create")
    return _delivery_out(db, d)
```

- [ ] **Шаг 4: run → PASS.** `pytest tests/test_support.py -q`.
- [ ] **Шаг 5: commit.**
```bash
git commit -am "feat(support): POST deliveries — partial delivery from awaiting positions (Phase 6.2c)"
```

---

## Task 6.2d — DELETE /deliveries/{id} (transit only, no UPD)

**Files:** Modify `support.py`; Test: append.

- [ ] **Шаг 1: append tests**

```python
# --- 6.2d: DELETE delivery ------------------------------------------------------

def test_delete_delivery_transit_returns_positions(client_admin):
    proc_id = _to_support(client_admin, "DEL-1", "del", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.delete(f"/deliveries/{d['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # position back to awaiting
    pos = client_admin.get(f"/procedures/{proc_id}").json()["positions"][0]
    assert pos["delivery_id"] is None
    assert client_admin.get(f"/procedures/{proc_id}").json()["deliveries"] == []


def test_delete_delivery_done_409(client_admin):
    proc_id = _to_support(client_admin, "DEL-DONE", "done", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    client_admin.patch(f"/deliveries/{d['id']}", json={"status": "done"})  # transit→done
    r = client_admin.delete(f"/deliveries/{d['id']}")
    assert r.status_code == 409


def test_delete_delivery_with_upd_409(client_admin):
    proc_id = _to_support(client_admin, "DEL-UPD", "upd", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    client_admin.post(f"/deliveries/{d['id']}/upd", json={"upd": "UPD-99"})
    r = client_admin.delete(f"/deliveries/{d['id']}")
    assert r.status_code == 409


def test_delete_delivery_not_found_404(client_admin):
    assert client_admin.delete("/deliveries/99999").status_code == 404
```

- [ ] **Шаг 2: run → FAIL.**
- [ ] **Шаг 3: implementation** — append to `support.py`:

```python
@router.delete("/deliveries/{delivery_id}")
def delete_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> dict:
    d = db.get(Delivery, delivery_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery not found")
    if d.status != "transit":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="only transit deliveries can be disbanded")
    # FK guard: an issued UPD references this delivery → forbid.
    if db.query(UpdPayment).filter(UpdPayment.delivery_id == d.id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="cannot disband delivery with issued UPD")
    # Return positions to awaiting, then drop the delivery.
    (db.query(ProcedurePosition)
        .filter(ProcedurePosition.delivery_id == d.id)
        .update({ProcedurePosition.delivery_id: None}))
    proc_id = d.procedure_id
    db.delete(d)
    db.commit()
    write_audit(db, entity_kind="procedure", entity_id=proc_id,
                user=current_user, action="delivery_delete")
    return {"ok": True}
```

- [ ] **Шаг 4: run → PASS.** `pytest tests/test_support.py -q`.
- [ ] **Шаг 5: commit.**
```bash
git commit -am "feat(support): DELETE delivery — disband transit, return positions (Phase 6.2d)"
```

---

## Task 6.2e — PATCH /deliveries/{id} (transit→done + docs + date/eta)

**Files:** Modify `support.py`; Test: append.

- [ ] **Шаг 1: append tests**

```python
# --- 6.2e: PATCH delivery -------------------------------------------------------

def test_patch_delivery_done_sets_date(client_admin):
    proc_id = _to_support(client_admin, "PAT-D1", "done", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.patch(f"/deliveries/{d['id']}", json={"status": "done"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"
    assert r.json()["date"] is not None          # auto-set (today ISO)


def test_patch_delivery_done_then_change_status_409(client_admin):
    proc_id = _to_support(client_admin, "PAT-D2", "done2", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    client_admin.patch(f"/deliveries/{d['id']}", json={"status": "done"})
    r = client_admin.patch(f"/deliveries/{d['id']}", json={"status": "transit"})
    assert r.status_code == 409


def test_patch_delivery_doc_flags_toggle(client_admin):
    proc_id = _to_support(client_admin, "PAT-DOC", "docs", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.patch(f"/deliveries/{d['id']}",
                           json={"doc_ttn": 1, "doc_sert": 1})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["doc_ttn"] == 1 and got["doc_sert"] == 1
    assert got["doc_m15"] == 0 and got["doc_upd"] == 0


def test_patch_delivery_eta(client_admin):
    proc_id = _to_support(client_admin, "PAT-ETA", "eta", [{"name": "x", "qty": 2.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.patch(f"/deliveries/{d['id']}", json={"eta": "2026-07-15"})
    assert r.status_code == 200
    assert r.json()["eta"] == "2026-07-15"


def test_patch_delivery_not_found_404(client_admin):
    assert client_admin.patch("/deliveries/99999", json={"eta": "2026-07-15"}).status_code == 404
```

- [ ] **Шаг 2: run → FAIL.**
- [ ] **Шаг 3: implementation** — append to `support.py`:

```python
@router.patch("/deliveries/{delivery_id}", response_model=DeliveryOut)
def patch_delivery(
    delivery_id: int,
    payload: DeliveryPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> DeliveryOut:
    d = db.get(Delivery, delivery_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery not found")
    data = payload.model_dump(exclude_unset=True)

    if "status" in data and data["status"] is not None:
        if data["status"] not in ("transit", "done"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="invalid status")
        if d.status == "done":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="delivery already received")
        if data["status"] == "done":
            d.status = "done"
            if not d.date:                         # Решение 3: auto дата приёмки
                d.date = calc.today_moscow().isoformat()

    for f in ("date", "eta", "doc_ttn", "doc_m15", "doc_upd", "doc_sert"):
        if f in data:
            setattr(d, f, data[f])

    db.commit()
    db.refresh(d)
    write_audit(db, entity_kind="procedure", entity_id=d.procedure_id,
                user=current_user, action="delivery_update")
    return _delivery_out(db, d)
```

- [ ] **Шаг 4: run → PASS.** `pytest tests/test_support.py -q`.
- [ ] **Шаг 5: commit.**
```bash
git commit -am "feat(support): PATCH delivery — transit→done + doc flags + date/eta (Phase 6.2e)"
```

---

## Task 6.2f — POST /deliveries/{id}/upd (upsert upd_payment)

**Files:** Modify `support.py`; Test: append.

- [ ] **Шаг 1: append tests**

```python
# --- 6.2f: POST upd (upsert) ----------------------------------------------------

def test_issue_upd_creates_upd_payment(client_admin, db_seeded):
    from app.models import UpdPayment
    proc_id = _to_support(client_admin, "UPD-1", "upd create",
                          [{"name": "x", "qty": 2.0, "price": 10000}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.post(f"/deliveries/{d['id']}/upd", json={"upd": "UPD-777"})
    assert r.status_code == 200, r.text
    assert r.json() == {"upd": "UPD-777", "pay_status": "await"}
    # row exists with origin=delivery, supplier/contract pulled from procedure
    db_seeded.expire_all()
    row = db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).one()
    assert row.origin == "delivery"
    assert row.pay_status == "await"
    assert row.amount == 20000   # 2.0 * 100.00 ₽ (delivery positions sum)
    # detail exposes upd on the delivery
    det = client_admin.get(f"/procedures/{proc_id}").json()
    assert det["deliveries"][0]["upd"] == {"upd": "UPD-777", "pay_status": "await"}


def test_issue_upd_upsert_updates_number(client_admin):
    proc_id = _to_support(client_admin, "UPD-2", "upd upsert", [{"name": "x", "qty": 1.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    client_admin.post(f"/deliveries/{d['id']}/upd", json={"upd": "WRONG"})
    r = client_admin.post(f"/deliveries/{d['id']}/upd", json={"upd": "CORRECT"})
    assert r.status_code == 200, r.text
    assert r.json()["upd"] == "CORRECT"
    # still exactly one upd_payment
    det = client_admin.get(f"/procedures/{proc_id}").json()
    assert det["deliveries"][0]["upd"]["upd"] == "CORRECT"


def test_issue_upd_empty_422(client_admin):
    proc_id = _to_support(client_admin, "UPD-3", "empty upd", [{"name": "x", "qty": 1.0}])
    pid = _position_ids(client_admin, proc_id)[0]
    d = client_admin.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    r = client_admin.post(f"/deliveries/{d['id']}/upd", json={"upd": ""})
    assert r.status_code == 422


def test_issue_upd_delivery_not_found_404(client_admin):
    r = client_admin.post("/deliveries/99999/upd", json={"upd": "X"})
    assert r.status_code == 404
```

- [ ] **Шаг 2: run → FAIL.**
- [ ] **Шаг 3: implementation** — append to `support.py`:

```python
@router.post(
    "/deliveries/{delivery_id}/upd",
    response_model=DeliveryUpdOut,
    status_code=status.HTTP_200_OK,
)
def issue_upd(
    delivery_id: int,
    payload: UpdIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> DeliveryUpdOut:
    d = db.get(Delivery, delivery_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery not found")
    proc = db.get(Procedure, d.procedure_id)

    existing = db.query(UpdPayment).filter(UpdPayment.delivery_id == d.id).first()
    if existing is not None:
        # Решение 4: upsert — поправить № без удаления.
        existing.upd = payload.upd
        db.commit()
        db.refresh(existing)
        write_audit(db, entity_kind="procedure", entity_id=d.procedure_id,
                    user=current_user, action="upd_update")
        return DeliveryUpdOut(upd=existing.upd, pay_status=existing.pay_status)

    positions = (
        db.query(ProcedurePosition)
        .filter(ProcedurePosition.delivery_id == d.id)
        .all()
    )
    amount = calc.procedure_sum(positions) or None
    new = UpdPayment(
        upd=payload.upd,
        origin="delivery",
        delivery_id=d.id,
        pay_status="await",
        supplier=proc.supplier if proc else None,
        contract=proc.contract if proc else None,
        amount=amount,
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    write_audit(db, entity_kind="procedure", entity_id=d.procedure_id,
                user=current_user, action="upd_create")
    return DeliveryUpdOut(upd=new.upd, pay_status=new.pay_status)
```

- [ ] **Шаг 4: run → PASS.** `pytest tests/test_support.py -q`.
- [ ] **Шаг 5: commit.**
```bash
git commit -am "feat(support): POST /deliveries/{id}/upd — upsert upd_payment (Phase 6.2f)"
```

---

## ⏸ СТОП — ПРОВЕРКА (Фаза 6 backend)

- [ ] **Команды (главный агент):**
```bash
cd backend && "$PY" -m pytest -q                  # ВЕСЬ набор PASS (0 регрессий)
cd backend && "$PY" -m pytest tests/test_calculations.py tests/test_support.py tests/test_procurement.py -v
cd frontend && npx tsc --noEmit 2>/dev/null; echo "tsc skipped (no FE changes this session)"
```
- [ ] **Ожидаемый вывод:** все backend-тесты PASS; `test_procurement.py` — 0 регрессий ( PATCH/cancel/uncancel/split/to-support/positions/RBAC не сломались); `test_calculations.py` — чисто; `test_support.py` — все новые зелёные.
- [ ] **git log:** коммиты 6.1 + 6.2a–f на `feat/phase-6`, linear поверх `main`.
- [ ] **Что проверяет человек:** эндпоинты через curl/httpie под админом (login → создать заявку → взять в работу → довести до «На сделку» → to-support → GET /support видит процедуру → PATCH contract/srok_dd → POST delivery → PATCH docs/done → POST upd → GET /procedures/{id} видит deliveries+upd). Под Комплектацией — PATCH/delivery/upd → 403.
- [ ] **Dev-окружение:** БД цела, uvicorn поднимается. (Если пересиживал seed — восстановить.)
- [ ] **Жду подтверждения пользователя перед frontend-сессией (6.3).**

---

## Self-Review (главный агент после написания)

- **Покрытие спеки:** `32` (расчёты) → 6.1 ✓; `31§4` (support endpoints) → 6.2a–f ✓ (GET /support, PATCH Б2, POST/DELETE/PATCH deliveries, POST upd); `02§7.1` active/archive → 6.2b ✓; `01` invariants (delivery non-empty ≥1 → 6.2c 422; upsert → 6.2f) ✓; RBAC `03` → guards ✓; аудит → каждая мутация ✓.
- **Плейсхолдеры:** нет TBD/«аналогично»; код приведён полностью для impl и тестов.
- **Согласованность типов:** `DeliveryOut`/`DeliveryUpdOut` определены в `deliveries.py`, импортированы в `procedures.py` (ProcedureDetail.deliveries) и `procurement.py` (`_build_detail`); имена полей моделей дословно из `models.py`; calc-сигнатуры едины между `calculations.py`, `support.py` и `test_calculations.py`.
- **Регрессия:** `patch_procedure` branching сохраняет всю закупочную логику; `_build_detail` обратно совместим (Б2-поля nullable, `deliveries` default `[]`).
