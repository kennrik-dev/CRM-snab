# Phase 7 «Оплаты» — Backend 7.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/payments` router + schemas + `payments_summary` so the «Оплаты» registry, manual УПД creation, payment card, edit, «Провести оплату», and summary all work end-to-end on the backend.

**Architecture:** One new FastAPI router `routers/payments.py` (prefix `/payments`, mirroring `support.py`/`requests.py` patterns) over the existing `upd_payment`/`upd_position` tables (no migration). One new pure-ish aggregate `calculations.payments_summary(db, today)` per `docs/32 §7`. New Pydantic schemas in `schemas/payments.py`. RBAC: mutations use `require_action("soprovozhdenie","edit")`; reads use `require_password_changed`. Audit under `entity_kind="upd_payment"`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2, pytest + httpx TestClient.

**Design spec:** `docs/superpowers/specs/2026-06-26-phase7-oplaty-design.md` (authoritative for decisions R1–R12).

## Global Constraints

- **Python interpreter (Windows):** `python` in Git Bash is the Store stub. Use `PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`; run tests as `cd backend && "$PY" -m pytest ...`. Do NOT use `backend/.venv`.
- **Money = INTEGER kopecks** end-to-end; **dates = ISO `YYYY-MM-DD` strings**. No `Decimal`/`datetime` on the wire.
- **Cyrillic search** must use `func.py_casefold(...)` + `func.instr(...)` (SQLite `lower()` is ASCII-only). Pattern is in `routers/support.py:97-110`.
- **Mutations:** `current_user: User = Depends(require_action("soprovozhdenie","edit"))` then `write_audit(db, entity_kind="upd_payment", entity_id=..., user=current_user, action=...)`. **Reads:** `_user: User = Depends(require_password_changed)`.
- **RBAC (R1):** a Сопровождение *employee* CAN mutate `/payments` (owns `soprovozhdenie`); a Комплектация/Закупки employee → 403. Админ → all.
- **Audit (R6):** `entity_kind="upd_payment"`, actions `payment_create`/`payment_patch`/`payment_pay`. (Existing `/deliveries/{id}/upd` stays `entity_kind="procedure"` — do not touch.)
- **No Alembic migration** — all columns exist since Phase 1/6.
- **Literal values (case-sensitive, CHECK-constrained):** `pay_status ∈ {'await','paid'}`; `origin ∈ {'delivery','manual','external'}`; procedure `status_postavki='Отменена'` = cancelled.
- **`pay` double-click → 409** (R5). Not-found → 404. Invalid → 422.
- **TDD per task:** red → green → commit. Commit message prefix `feat(payments):` (or `test(payments):`).
- After all tasks: full `pytest -q` green (no regressions) + curl smoke, then **⏸ STOP** for user.

## File Structure

- **Create** `backend/app/schemas/payments.py` — all Pydantic models for `/payments` (one responsibility: payment DTOs).
- **Create** `backend/app/routers/payments.py` — the `/payments` router (registry, manual create, detail, patch, pay, summary). Mirrors `support.py`.
- **Create** `backend/tests/test_payments.py` — one test module (self-contained fixtures mirroring `tests/test_support.py`).
- **Modify** `backend/app/calculations.py` — add `payments_summary(db, today)`.
- **Modify** `backend/app/main.py` — register the payments router.

Decomposition rationale: schemas are foundational (defined once in Task 1); the router grows endpoint-by-endpoint (Tasks 1–6); the summary aggregate is the most intricate piece and lands last (Task 6) with fixture-based math tests.

---

## Task 1: Schemas + router skeleton + `GET /payments` registry

**Files:**
- Create: `backend/app/schemas/payments.py`
- Create: `backend/app/routers/payments.py`
- Modify: `backend/app/main.py:3` (import) and `:6-12` (include router)
- Test: `backend/tests/test_payments.py`

**Interfaces:**
- Consumes: `app.audit.paginate`, `app.calculations` (`today_moscow`, `is_upd_overdue`), `app.dependencies.require_password_changed`, `app.models` (`UpdPayment`, `Delivery`, `Procedure`, `Tender`, `ParentRequest`, `User`), `app.permissions.require_action`, `app.db.get_db`.
- Produces: `router` (registered as `/payments`); schemas `PaymentListItem`, `PaginatedPayments`, `PaymentCreate`, `PaymentPatch`, `PaymentDetail`, `PaymentDeliveryOut`, `UpdPositionIn`, `UpdPositionOut`, `PaymentsSummary`, `SummaryMeters`, `SummaryBar` (all defined here for later tasks).

- [ ] **Step 1: Write `backend/app/schemas/payments.py` (complete)**

```python
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
```

- [ ] **Step 2: Write `backend/app/routers/payments.py` (skeleton + list endpoint)**

```python
"""/payments router (Phase 7.1) — реестр УПД, ручное создание, карточка,
редактирование, «Провести оплату», сводка.

RBAC: мутации — require_action('soprovozhdenie','edit'); чтение — require_password_changed.
Audit: entity_kind='upd_payment'. Spec: docs/31-api.md §5, docs/32 §7.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import calculations as calc
from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import (
    Delivery,
    ParentRequest,
    Procedure,
    Tender,
    UpdPayment,
    User,
)
from app.permissions import require_action
from app.schemas.payments import (
    PaginatedPayments,
    PaymentListItem,
)


router = APIRouter(prefix="/payments", tags=["payments"])

_SORT_KEYS = {
    "created_at", "upd", "request", "supplier", "contract",
    "zrds", "status", "srok", "amount",
}


def _not_cancelled():
    """WHERE clause: procedure is absent (manual УПД) OR not 'Отменена'."""
    return or_(
        Procedure.status_postavki.is_(None),
        Procedure.status_postavki != "Отменена",
    )


@router.get("", response_model=PaginatedPayments)
def list_payments(
    search: Optional[str] = Query(None),
    hide_paid: bool = Query(False, description="Скрыть оплаченные"),
    sort: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaginatedPayments:
    q = (
        db.query(UpdPayment, ParentRequest.code, Delivery.n)
        .join(Delivery, UpdPayment.delivery_id == Delivery.id, isouter=True)
        .join(Procedure, Delivery.procedure_id == Procedure.id, isouter=True)
        .join(Tender, Procedure.tender_id == Tender.id, isouter=True)
        .join(ParentRequest, Tender.parent_id == ParentRequest.id, isouter=True)
        .filter(_not_cancelled())
    )

    if hide_paid:
        q = q.filter(UpdPayment.pay_status != "paid")

    if search:
        s = search.strip()
        if s:
            cf = s.casefold()
            q = q.filter(
                or_(
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.upd, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.request_label, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(ParentRequest.code, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.supplier, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.contract, "")), cf) > 0,
                    func.instr(func.py_casefold(func.coalesce(UpdPayment.zrds, "")), cf) > 0,
                )
            )

    if sort not in _SORT_KEYS:
        sort = "created_at"
    _order = lambda col: col.asc().nulls_last()
    if sort == "created_at":
        q = q.order_by(UpdPayment.created_at.desc(), UpdPayment.id.desc())
    elif sort == "upd":
        q = q.order_by(_order(UpdPayment.upd), UpdPayment.id.asc())
    elif sort == "request":
        q = q.order_by(_order(ParentRequest.code), UpdPayment.id.asc())
    elif sort == "supplier":
        q = q.order_by(_order(UpdPayment.supplier), UpdPayment.id.asc())
    elif sort == "contract":
        q = q.order_by(_order(UpdPayment.contract), UpdPayment.id.asc())
    elif sort == "zrds":
        q = q.order_by(_order(UpdPayment.zrds), UpdPayment.id.asc())
    elif sort == "status":
        q = q.order_by(_order(UpdPayment.pay_status), UpdPayment.id.asc())
    elif sort == "srok":
        q = q.order_by(_order(UpdPayment.srok), UpdPayment.id.asc())
    elif sort == "amount":
        q = q.order_by(_order(UpdPayment.amount), UpdPayment.id.asc())

    page_data = paginate(q, page=page, page_size=page_size)
    today = calc.today_moscow()
    items: list[PaymentListItem] = []
    for row in page_data["items"]:
        upd, parent_code, delivery_n = row
        if upd.origin == "manual":
            request_display = upd.request_label
        else:
            request_display = parent_code or upd.request_label
        items.append(
            PaymentListItem(
                id=upd.id,
                upd=upd.upd,
                origin=upd.origin,
                request_display=request_display,
                supplier=upd.supplier,
                contract=upd.contract,
                zrds=upd.zrds,
                delivery_n=delivery_n if upd.origin == "delivery" else None,
                pay_status=upd.pay_status,
                is_overdue=calc.is_upd_overdue(upd, today),
                srok=upd.srok,
                pay_date=upd.pay_date,
                amount=upd.amount,
                created_at=upd.created_at,
            )
        )
    return PaginatedPayments(items=items, total=page_data["total"])
```

- [ ] **Step 3: Register the router in `backend/app/main.py`**

Change line 3 import to include `payments` (keep alphabetical):

```python
from app.routers import auth, dict, payments, procurement, requests, search, support, users
```

Add the include (after `app.include_router(support.router)`):

```python
app.include_router(payments.router)
```

- [ ] **Step 4: Write the failing tests in `backend/tests/test_payments.py`**

Create the file with self-contained fixtures (mirroring `tests/test_support.py`) plus the Task 1 tests. (Tasks 2–6 append tests to this same file; these fixtures stay in scope.)

```python
"""Tests for /payments router (Phase 7.1).

Pattern mirrors tests/test_support.py: self-contained seeded fixtures,
client_admin (seeded admin, password changed), and role helpers.
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


# --- fixtures (mirror test_support.py) -----------------------------------------

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


# --- helpers -------------------------------------------------------------------

def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_support(client, code, title, positions):
    """parent + positions → take-to-work → price → 'На сделку' → to-support.
    Returns procedure_id (block=soprovozhdenie)."""
    body = _create_request(client, code, title, positions)
    parent_id = body["id"]
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    proc_id = r.json()["procedure_id"]
    proc_positions = client.get(f"/procedures/{proc_id}").json()["positions"]
    for src, proc_pos in zip(positions, proc_positions):
        if src.get("price") is not None:
            client.patch(
                f"/procedures/{proc_id}/positions/{proc_pos['id']}",
                json={"price": src["price"]},
            )
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r2 = client.post(f"/procedures/{proc_id}/to-support")
    assert r2.status_code == 200, r2.text
    return proc_id


def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def _delivery_upd(client, code, title, positions):
    """Procedure → delivery of position 0 → issue УПД. Returns (proc_id, delivery, upd_resp)."""
    proc_id = _to_support(client, code, title, positions)
    pid = _position_ids(client, proc_id)[0]
    d = client.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    upd = client.post(f"/deliveries/{d['id']}/upd", json={"upd": "UPD-" + code}).json()
    return proc_id, d, upd


def _make_soprov_emp(db, email="soprov_emp@crm.local"):
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


# --- 7.1 Task 1: GET /payments registry ----------------------------------------

def test_payments_list_empty(client_admin):
    r = client_admin.get("/payments")
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [], "total": 0}


def test_payments_list_shows_delivery_upd_with_joined_fields(client_admin):
    proc_id, d, upd = _delivery_upd(
        client_admin, "PAY-L1", "list one",
        [{"name": "x", "qty": 2.0, "price": 10000}],
    )
    r = client_admin.get("/payments")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["upd"] == "UPD-PAY-L1"
    assert item["origin"] == "delivery"
    assert item["request_display"] == "PAY-L1"      # parent_request.code
    assert item["delivery_n"] == 1
    assert item["pay_status"] == "await"
    assert item["amount"] == 20000                  # 2.0 * 100.00 ₽
    assert item["is_overdue"] is False              # no srok


def test_payments_list_upd_overdue_flag(client_admin, db_seeded):
    from app.models import UpdPayment
    proc_id, d, _upd = _delivery_upd(
        client_admin, "PAY-OVD", "overdue",
        [{"name": "x", "qty": 1.0, "price": 5000}],
    )
    # srok в прошлом (PATCH появляется в Задаче 4 — пока напрямую через БД)
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": "2026-06-01"})
    db_seeded.commit()
    item = client_admin.get("/payments").json()["items"][0]
    assert item["is_overdue"] is True


def test_payments_list_excludes_cancelled_procedure(client_admin):
    proc_id, d, _upd = _delivery_upd(
        client_admin, "PAY-CXL", "cancel",
        [{"name": "x", "qty": 1.0, "price": 1000}],
    )
    # процедура в отмене → её УПД исчезает из реестра
    client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Отменена"})
    body = client_admin.get("/payments").json()
    assert body["total"] == 0
```

- [ ] **Step 5: Run tests to verify they fail (red)**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -v`
Expected: collection fails or 404 on `/payments` (router not yet effective until main.py edit in step 3 — but main.py is edited in this task). After steps 1–3 the list endpoint exists, so the empty test passes and the others should pass too. To enforce red-first: write the test file (step 4) and run BEFORE creating `payments.py` (steps 1–3). I.e. order: step 4 (tests) → run (red, 404) → steps 1–3 (impl) → run (green).
Expected red output: `404 NOT FOUND` on `GET /payments`.

- [ ] **Step 6: Run tests to verify they pass (green)**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/payments.py backend/app/routers/payments.py backend/app/main.py backend/tests/test_payments.py
git commit -m "feat(payments): registry GET /payments + schemas (Phase 7.1 T1)"
```

---

## Task 2: `POST /payments` (manual УПД) + `_detail` helper

**Files:**
- Modify: `backend/app/routers/payments.py` (add imports `UpdPosition`, `PaymentCreate`, `PaymentDetail`, `PaymentDeliveryOut`, `UpdPositionOut`; add `_detail` helper + `create_payment` endpoint)
- Test: `backend/tests/test_payments.py` (append)

**Interfaces:**
- Consumes: `PaymentCreate`, `UpdPosition` (model), `calc.procedure_sum` (works on Pydantic `UpdPositionIn` via `.qty`/`.price`).
- Produces: `_detail(db, upd) -> PaymentDetail` (reused by Tasks 3–5); `POST /payments` → 201 `PaymentDetail`.

- [ ] **Step 1: Add the failing tests (append to `backend/tests/test_payments.py`)**

```python
# --- 7.1 Task 2: POST /payments (manual УПД) -----------------------------------

def test_create_manual_upd_happy(client_admin, db_seeded):
    from app.models import UpdPayment
    r = client_admin.post("/payments", json={
        "upd": "UPD-MAN-1", "request_label": "Т-99 №3",
        "supplier": "ООО Ромашка", "srok": "2026-12-31",
        "amount": 1500000, "zrds": "ЗРДС-5",
        "positions": [{"n": 1, "name": "болт", "unit": "шт", "qty": 10.0, "price": 150000}],
    })
    assert r.status_code == 201, r.text
    got = r.json()
    assert got["origin"] == "manual"
    assert got["pay_status"] == "await"
    assert got["amount"] == 1500000
    assert got["delivery_id"] is None
    assert got["delivery"] is None
    assert len(got["positions"]) == 1
    assert got["positions"][0]["name"] == "болт"
    # persisted
    db_seeded.expire_all()
    row = db_seeded.query(UpdPayment).filter_by(upd="UPD-MAN-1").one()
    assert row.origin == "manual"
    assert row.contract is None              # у manual нет договора при создании


def test_create_manual_upd_amount_from_positions(client_admin):
    r = client_admin.post("/payments", json={
        "upd": "UPD-MAN-2", "supplier": "С",
        "positions": [{"qty": 2.0, "price": 5000}, {"qty": 1.0, "price": 10000}],
    })
    assert r.status_code == 201, r.text
    assert r.json()["amount"] == 20000       # 2*5000 + 1*10000


def test_create_manual_upd_empty_upd_422(client_admin):
    r = client_admin.post("/payments", json={"upd": ""})
    assert r.status_code == 422


def test_create_manual_upd_rbac_ok_for_soprov_emp(client_seeded, db_seeded, client_admin):
    _ = client_admin  # seed/seed admin not strictly needed but keeps fixtures warm
    u = _make_soprov_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.post("/payments", json={"upd": "UPD-EMP", "supplier": "S"})
    assert r.status_code == 201, r.text


def test_create_manual_upd_rbac_403_for_kompl_emp(client_seeded, db_seeded, client_admin):
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.post("/payments", json={"upd": "UPD-KOMPL", "supplier": "S"})
    assert r.status_code == 403


def test_create_manual_upd_writes_audit(client_admin, db_seeded):
    from app.models import AuditLog, UpdPayment
    client_admin.post("/payments", json={"upd": "UPD-AUD", "supplier": "S"})
    db_seeded.expire_all()
    payment = db_seeded.query(UpdPayment).filter_by(upd="UPD-AUD").one()
    rows = db_seeded.query(AuditLog).filter_by(
        entity_kind="upd_payment", entity_id=payment.id, action="payment_create"
    ).all()
    assert len(rows) == 1


def test_manual_upd_appears_in_list(client_admin):
    client_admin.post("/payments", json={
        "upd": "UPD-MAN-L", "request_label": "Т-70 №1", "supplier": "Поставщик",
    })
    body = client_admin.get("/payments").json()
    item = next(i for i in body["items"] if i["upd"] == "UPD-MAN-L")
    assert item["origin"] == "manual"
    assert item["request_display"] == "Т-70 №1"
    assert item["delivery_n"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "manual or create_manual" -v`
Expected: FAIL — `POST /payments` → 404 (endpoint not defined yet).

- [ ] **Step 3: Add `_detail` helper + `create_payment` to `backend/app/routers/payments.py`**

Extend the model import to include `UpdPosition`, and the schema import to include `PaymentCreate`, `PaymentDetail`, `PaymentDeliveryOut`, `UpdPositionOut`:

```python
from app.models import (
    Delivery,
    ParentRequest,
    Procedure,
    Tender,
    UpdPayment,
    UpdPosition,
    User,
)
from app.schemas.payments import (
    PaginatedPayments,
    PaymentCreate,
    PaymentDetail,
    PaymentDeliveryOut,
    PaymentListItem,
    UpdPositionOut,
)
```

Add the helper + endpoint (after `list_payments`):

```python
def _detail(db: Session, upd: UpdPayment) -> PaymentDetail:
    positions = (
        db.query(UpdPosition)
        .filter(UpdPosition.upd_payment_id == upd.id)
        .order_by(UpdPosition.id.asc())
        .all()
    )
    delivery = None
    if upd.delivery_id is not None:
        d = db.get(Delivery, upd.delivery_id)
        if d is not None:
            parent_code = None
            proc = db.get(Procedure, d.procedure_id)
            if proc is not None:
                tender = db.get(Tender, proc.tender_id)
                if tender is not None:
                    parent = db.get(ParentRequest, tender.parent_id)
                    parent_code = parent.code if parent else None
            delivery = PaymentDeliveryOut(
                n=d.n, procedure_id=d.procedure_id, parent_code=parent_code
            )
    return PaymentDetail(
        id=upd.id,
        upd=upd.upd,
        origin=upd.origin,
        delivery_id=upd.delivery_id,
        request_label=upd.request_label,
        supplier=upd.supplier,
        contract=upd.contract,
        zrds=upd.zrds,
        srok=upd.srok,
        amount=upd.amount,
        pay_status=upd.pay_status,
        pay_date=upd.pay_date,
        created_at=upd.created_at,
        positions=[UpdPositionOut.model_validate(p) for p in positions],
        delivery=delivery,
        is_overdue=calc.is_upd_overdue(upd, calc.today_moscow()),
    )


@router.post("", response_model=PaymentDetail, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> PaymentDetail:
    amount = payload.amount
    if amount is None and payload.positions:
        amount = calc.procedure_sum(payload.positions) or None
    new = UpdPayment(
        upd=payload.upd,
        origin="manual",
        delivery_id=None,
        request_label=payload.request_label,
        supplier=payload.supplier,
        contract=None,
        zrds=payload.zrds,
        srok=payload.srok,
        amount=amount,
        pay_status="await",
    )
    db.add(new)
    db.flush()  # assign new.id
    if payload.positions:
        for i, p in enumerate(payload.positions, start=1):
            db.add(
                UpdPosition(
                    upd_payment_id=new.id,
                    n=p.n if p.n is not None else i,
                    name=p.name,
                    unit=p.unit,
                    qty=p.qty,
                    price=p.price,
                )
            )
    db.commit()
    db.refresh(new)
    write_audit(
        db, entity_kind="upd_payment", entity_id=new.id,
        user=current_user, action="payment_create",
    )
    return _detail(db, new)
```

- [ ] **Step 4: Run tests to verify they pass (green)**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "manual or create_manual" -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/payments.py backend/tests/test_payments.py
git commit -m "feat(payments): POST /payments manual УПД + _detail helper (Phase 7.1 T2)"
```

---

## Task 3: `GET /payments/{id}` (payment card)

**Files:**
- Modify: `backend/app/routers/payments.py` (add `get_payment`)
- Test: `backend/tests/test_payments.py` (append)

**Interfaces:**
- Consumes: `_detail` (Task 2).
- Produces: `GET /payments/{payment_id}` → `PaymentDetail` (404 if missing).

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 7.1 Task 3: GET /payments/{id} (detail) -----------------------------------

def test_get_payment_detail_delivery_origin(client_admin):
    proc_id, d, _upd = _delivery_upd(
        client_admin, "PAY-DET", "detail",
        [{"name": "x", "qty": 1.0, "price": 7000}],
    )
    list_item = client_admin.get("/payments").json()["items"][0]
    pid = list_item["id"]
    r = client_admin.get(f"/payments/{pid}")
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["origin"] == "delivery"
    assert got["amount"] == 7000
    assert got["delivery"] == {"n": 1, "procedure_id": proc_id, "parent_code": "PAY-DET"}
    assert got["is_overdue"] is False


def test_get_payment_detail_manual_origin(client_admin):
    created = client_admin.post("/payments", json={
        "upd": "UPD-DET-M", "request_label": "Т-1", "supplier": "S",
        "positions": [{"name": "гайка", "qty": 3.0, "price": 1000}],
    }).json()
    r = client_admin.get(f"/payments/{created['id']}")
    assert r.status_code == 200
    got = r.json()
    assert got["delivery"] is None
    assert got["positions"][0]["name"] == "гайка"


def test_get_payment_not_found_404(client_admin):
    assert client_admin.get("/payments/99999").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "get_payment" -v`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Add `get_payment` to `backend/app/routers/payments.py`**

```python
@router.get("/{payment_id}", response_model=PaymentDetail)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaymentDetail:
    upd = db.get(UpdPayment, payment_id)
    if upd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return _detail(db, upd)
```

> Route order: this is defined AFTER `GET ""` (list) and there is no `/summary` yet. Task 6 adds `GET /summary` — it MUST be placed ABOVE `/{payment_id}` in the file so `"summary"` is not captured by `{payment_id}`. Keep that ordering when adding the summary route.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "get_payment" -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/payments.py backend/tests/test_payments.py
git commit -m "feat(payments): GET /payments/{id} card (Phase 7.1 T3)"
```

---

## Task 4: `PATCH /payments/{id}`

**Files:**
- Modify: `backend/app/routers/payments.py` (add `PaymentPatch` to imports + `patch_payment`)
- Test: `backend/tests/test_payments.py` (append)

**Interfaces:**
- Consumes: `PaymentPatch`, `_detail`, `UpdPosition`.
- Produces: `PATCH /payments/{payment_id}` → `PaymentDetail` (positions = full replace; 404 if missing).

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 7.1 Task 4: PATCH /payments/{id} ------------------------------------------

def test_patch_payment_fields_persist(client_admin):
    created = client_admin.post("/payments", json={
        "upd": "UPD-PAT", "supplier": "S", "amount": 1000,
    }).json()
    r = client_admin.patch(f"/payments/{created['id']}", json={
        "srok": "2026-08-01", "zrds": "ЗРДС-9", "contract": "ДК-1",
        "supplier": "ООО Дуб", "amount": 999000,
    })
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["srok"] == "2026-08-01"
    assert got["zrds"] == "ЗРДС-9"
    assert got["contract"] == "ДК-1"
    assert got["supplier"] == "ООО Дуб"
    assert got["amount"] == 999000


def test_patch_payment_positions_replace(client_admin):
    created = client_admin.post("/payments", json={
        "upd": "UPD-PATPOS", "supplier": "S",
        "positions": [{"name": "a", "qty": 1.0, "price": 100}],
    }).json()
    r = client_admin.patch(f"/payments/{created['id']}", json={
        "positions": [{"name": "b", "qty": 2.0, "price": 200},
                      {"name": "c", "qty": 3.0, "price": 300}],
    })
    assert r.status_code == 200, r.text
    names = [p["name"] for p in r.json()["positions"]]
    assert names == ["b", "c"]            # old "a" gone → full replace


def test_patch_payment_rbac_403_for_kompl(client_seeded, db_seeded, client_admin):
    created = client_admin.post("/payments", json={"upd": "UPD-PATR", "supplier": "S"}).json()
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.patch(f"/payments/{created['id']}", json={"supplier": "X"})
    assert r.status_code == 403


def test_patch_payment_writes_audit(client_admin, db_seeded):
    from app.models import AuditLog
    created = client_admin.post("/payments", json={"upd": "UPD-PATAD", "supplier": "S"}).json()
    client_admin.patch(f"/payments/{created['id']}", json={"amount": 5000})
    db_seeded.expire_all()
    rows = db_seeded.query(AuditLog).filter_by(
        entity_kind="upd_payment", entity_id=created["id"], action="payment_patch"
    ).all()
    assert len(rows) == 1


def test_patch_payment_not_found_404(client_admin):
    assert client_admin.patch("/payments/99999", json={"amount": 1}).status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "patch_payment" -v`
Expected: FAIL — `PATCH /payments/{id}` → 405/404.

- [ ] **Step 3: Add `PaymentPatch` to the schema import and `patch_payment` endpoint**

Add `PaymentPatch` to the `from app.schemas.payments import (...)` block.

```python
@router.patch("/{payment_id}", response_model=PaymentDetail)
def patch_payment(
    payment_id: int,
    payload: PaymentPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> PaymentDetail:
    upd = db.get(UpdPayment, payment_id)
    if upd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    data = payload.model_dump(exclude_unset=True)
    for f in ("srok", "zrds", "contract", "supplier", "amount"):
        if f in data:
            setattr(upd, f, data[f])
    if "positions" in data:
        # полная замена строк upd_position
        db.query(UpdPosition).filter(UpdPosition.upd_payment_id == upd.id).delete()
        for i, p in enumerate(payload.positions or [], start=1):
            db.add(
                UpdPosition(
                    upd_payment_id=upd.id,
                    n=p.n if p.n is not None else i,
                    name=p.name,
                    unit=p.unit,
                    qty=p.qty,
                    price=p.price,
                )
            )
    db.commit()
    db.refresh(upd)
    write_audit(
        db, entity_kind="upd_payment", entity_id=upd.id,
        user=current_user, action="payment_patch",
    )
    return _detail(db, upd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "patch_payment" -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/payments.py backend/tests/test_payments.py
git commit -m "feat(payments): PATCH /payments/{id} (Phase 7.1 T4)"
```

---

## Task 5: `POST /payments/{id}/pay` («Провести оплату») + `hide_paid`

**Files:**
- Modify: `backend/app/routers/payments.py` (add `pay_payment`)
- Test: `backend/tests/test_payments.py` (append)

**Interfaces:**
- Consumes: `_detail`, `calc.today_moscow`.
- Produces: `POST /payments/{payment_id}/pay` → `PaymentDetail`; await→paid + `pay_date`; double → 409; 404 if missing.

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 7.1 Task 5: POST /payments/{id}/pay ---------------------------------------

def test_pay_payment_sets_paid_and_date(client_admin):
    created = client_admin.post("/payments", json={
        "upd": "UPD-PAY", "supplier": "S", "amount": 500000,
    }).json()
    r = client_admin.post(f"/payments/{created['id']}/pay")
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["pay_status"] == "paid"
    assert got["pay_date"] is not None           # ISO today
    assert got["is_overdue"] is False            # paid → never overdue


def test_pay_payment_double_409(client_admin):
    created = client_admin.post("/payments", json={"upd": "UPD-PAY2", "supplier": "S"}).json()
    client_admin.post(f"/payments/{created['id']}/pay")
    r = client_admin.post(f"/payments/{created['id']}/pay")
    assert r.status_code == 409


def test_pay_payment_not_found_404(client_admin):
    assert client_admin.post("/payments/99999/pay").status_code == 404


def test_pay_payment_rbac_403_for_kompl(client_seeded, db_seeded, client_admin):
    created = client_admin.post("/payments", json={"upd": "UPD-PAYR", "supplier": "S"}).json()
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    r = client_seeded.post(f"/payments/{created['id']}/pay")
    assert r.status_code == 403


def test_pay_payment_writes_audit(client_admin, db_seeded):
    from app.models import AuditLog
    created = client_admin.post("/payments", json={"upd": "UPD-PAYAD", "supplier": "S"}).json()
    client_admin.post(f"/payments/{created['id']}/pay")
    db_seeded.expire_all()
    rows = db_seeded.query(AuditLog).filter_by(
        entity_kind="upd_payment", entity_id=created["id"], action="payment_pay"
    ).all()
    assert len(rows) == 1


def test_list_hide_paid_excludes_paid(client_admin):
    created = client_admin.post("/payments", json={"upd": "UPD-HIDE", "supplier": "S"}).json()
    client_admin.post(f"/payments/{created['id']}/pay")
    all_items = client_admin.get("/payments").json()["items"]
    hidden = client_admin.get("/payments?hide_paid=true").json()["items"]
    assert any(i["upd"] == "UPD-HIDE" for i in all_items)
    assert not any(i["upd"] == "UPD-HIDE" for i in hidden)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "pay_payment or hide_paid" -v`
Expected: FAIL — `POST /payments/{id}/pay` → 404/405.

- [ ] **Step 3: Add `pay_payment` to `backend/app/routers/payments.py`**

```python
@router.post("/{payment_id}/pay", response_model=PaymentDetail)
def pay_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_action("soprovozhdenie", "edit")),
) -> PaymentDetail:
    upd = db.get(UpdPayment, payment_id)
    if upd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    if upd.pay_status == "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="payment already paid")
    upd.pay_status = "paid"
    upd.pay_date = calc.today_moscow().isoformat()
    db.commit()
    db.refresh(upd)
    write_audit(
        db, entity_kind="upd_payment", entity_id=upd.id,
        user=current_user, action="payment_pay",
    )
    return _detail(db, upd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "pay_payment or hide_paid" -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/payments.py backend/tests/test_payments.py
git commit -m "feat(payments): POST /payments/{id}/pay «Провести оплату» (Phase 7.1 T5)"
```

---

## Task 6: `calculations.payments_summary` + `GET /payments/summary`

**Files:**
- Modify: `backend/app/calculations.py` (add `payments_summary`)
- Modify: `backend/app/routers/payments.py` (add `PaymentsSummary`/`SummaryMeters`/`SummaryBar` to imports + `payments_summary_endpoint` route ABOVE `/{payment_id}`)
- Test: `backend/tests/test_payments.py` (append)

**Interfaces:**
- Consumes: `position_sum`, `is_upd_overdue` (module-level pure helpers); models via local import inside the function.
- Produces: `calc.payments_summary(db, today) -> {"meters": {...}, "bar": {...}}`; `GET /payments/summary` → `PaymentsSummary`.

**Authority for the math:** `docs/32-calculations.md §7`. Interpretation locked here (R12):
- `meters.paid = Σ amount` of paid УПД (excl cancelled-procedure).
- `meters.await_ = Σ amount` of await УПД (excl cancelled-procedure).
- `meters.overdue = Σ amount` of await УПД with `is_upd_overdue` (srok<today).
- `meters.in_work = meters.paid + meters.await_`.
- `bar.paid = meters.paid`; `bar.await_ = meters.await_`.
- `bar.delivered_no_upd = Σ position_sum` of delivered positions (`delivery_id` set) whose delivery has **no** `upd_payment`.
- `bar.contracted_no_delivery = Σ position_sum` of positions of procedures that have **no** delivery.
- “Active procedure” = `status_postavki IS NULL OR status_postavki != 'Отменена'` (manual УПД and not-yet-supported procedures are included).

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 7.1 Task 6: payments_summary + GET /payments/summary ----------------------

def test_summary_meters_paid_await_overdue(client_admin):
    # 2 manual УПД: one paid 1000000, one await 500000 with past srok → overdue
    a = client_admin.post("/payments", json={
        "upd": "UPD-SUM-A", "amount": 1000000,
    }).json()
    client_admin.post(f"/payments/{a['id']}/pay")
    b = client_admin.post("/payments", json={
        "upd": "UPD-SUM-B", "amount": 500000, "srok": "2026-06-01",  # past → overdue
    }).json()
    r = client_admin.get("/payments/summary")
    assert r.status_code == 200, r.text
    m = r.json()["meters"]
    assert m["paid"] == 1000000
    assert m["await_"] == 500000
    assert m["overdue"] == 500000
    assert m["in_work"] == 1500000


def test_summary_bar_segments(client_admin):
    """Один delivery-УПД (покрыт) + одна доставленная позиция без УПД +
    одна позиция в процедуре без поставки."""
    # 1) delivery УПД paid — covered delivery
    proc_id, d, _upd = _delivery_upd(
        client_admin, "SUM-DEL", "del",
        [{"name": "x", "qty": 1.0, "price": 300000}],
    )
    list_id = client_admin.get("/payments").json()["items"][0]["id"]
    client_admin.post(f"/payments/{list_id}/pay")
    # 2) delivered position with NO УПД → delivered_no_upd
    proc2 = _to_support(client_admin, "SUM-NOUPD", "no_upd",
                        [{"name": "y", "qty": 1.0, "price": 200000}])
    pid2 = _position_ids(client_admin, proc2)[0]
    client_admin.post(f"/procedures/{proc2}/deliveries", json={"positions": [pid2]})
    # 3) procedure with positions but NO delivery → contracted_no_delivery
    _to_support(client_admin, "SUM-NODEL", "no_del",
                [{"name": "z", "qty": 1.0, "price": 400000}])
    bar = client_admin.get("/payments/summary").json()["bar"]
    assert bar["paid"] == 300000
    assert bar["await_"] == 0
    assert bar["delivered_no_upd"] == 200000
    assert bar["contracted_no_delivery"] == 400000


def test_summary_excludes_cancelled_procedure(client_admin):
    proc_id, d, _upd = _delivery_upd(
        client_admin, "SUM-CXL", "cxl",
        [{"name": "x", "qty": 1.0, "price": 100000}],
    )
    client_admin.patch(f"/procedures/{proc_id}", json={"status_postavki": "Отменена"})
    m = client_admin.get("/payments/summary").json()["meters"]
    assert m["paid"] == 0 and m["await_"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "summary" -v`
Expected: FAIL — `GET /payments/summary` → 404 (route + function missing).

- [ ] **Step 3: Add `payments_summary` to `backend/app/calculations.py`**

Append after `is_upd_overdue` (and add to `__all__`):

```python
def payments_summary(db, today: date) -> dict:
    """Сводка «Оплаты» (docs/32 §7). Суммы — int коп. (None-amount → 0).
    Исключает УПД отменённых процедур; manual-УПД (без процедуры) учитываются.

    Returns {"meters": {paid, await_, overdue, in_work},
             "bar": {paid, await_, delivered_no_upd, contracted_no_delivery}}.
    """
    from app.models import (
        Delivery, ParentRequest, Procedure, ProcedurePosition, Tender, UpdPayment,
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
```

Add to the `__all__` list in `calculations.py`:
```python
    "payments_summary",
```

Also add the `or_` import at the top of `calculations.py` (it is not currently imported):
```python
from sqlalchemy import or_
```

- [ ] **Step 4: Add the `GET /payments/summary` route to `backend/app/routers/payments.py`**

Add to the schema import: `PaymentsSummary`, `SummaryBar`, `SummaryMeters`.

Place this route ABOVE `@router.get("/{payment_id}", ...)` so `"summary"` is matched literally before the `{payment_id}` path param:

```python
@router.get("/summary", response_model=PaymentsSummary)
def payments_summary_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> PaymentsSummary:
    data = calc.payments_summary(db, calc.today_moscow())
    return PaymentsSummary(
        meters=SummaryMeters(**data["meters"]),
        bar=SummaryBar(**data["bar"]),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_payments.py -k "summary" -v`
Expected: 3 passed.

- [ ] **Step 6: Run the FULL backend suite (no regressions)**

Run: `cd backend && "$PY" -m pytest -q`
Expected: all green (previous total + new test_payments tests, 0 failures).

- [ ] **Step 7: Commit**

```bash
git add backend/app/calculations.py backend/app/routers/payments.py backend/tests/test_payments.py
git commit -m "feat(payments): payments_summary + GET /payments/summary (Phase 7.1 T6)"
```

---

## ⏸ STOP — Phase 7.1 verification (before Frontend 7.2)

- [ ] `cd backend && "$PY" -m pytest -q` → all green, 0 failures.
- [ ] Manual curl smoke (dev server on :8000, logged in as admin via cookie) — or via TestClient spot-check:
  - `GET /payments` → registry (incl. Phase-6 delivery УПД if present in dev DB).
  - `POST /payments` `{upd, supplier, srok, amount}` → 201 manual УПД.
  - `POST /payments/{id}/pay` → `paid` + `pay_date`.
  - `GET /payments/summary` → `{meters, bar}`.
- [ ] **Wait for user confirmation before Frontend 7.2.**

🔎 After Frontend 7.2 (next session): ui-checker on the «Оплаты» page + PaymentCard.
