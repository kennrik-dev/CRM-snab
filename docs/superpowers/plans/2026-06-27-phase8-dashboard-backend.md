# Phase 8 «Дашборд» — Backend 8.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `GET /dashboard` + `calculations.dashboard(db, today)` so the overview screen (6 meters, 4-stage flow, 2-tier «Требует внимания», 20-item audit «Лента событий», 3 compact tables) is served end-to-end on the backend.

**Architecture:** One new FastAPI router `routers/dashboard.py` (prefix `/dashboard`, read-only, auth = `require_password_changed` — identical for all roles, global data) over existing tables (no migration). One new aggregate `calculations.dashboard(db, today)` per `docs/32 §6` + spec R1–R10, built from a shared `_load_dashboard_ctx` + thin formatters (`_dash_meters/_dash_flow/_dash_attention/_dash_feed/_dash_tables`), reusing existing pure helpers (`is_procedure_overdue`, `is_delivery_overdue`, `is_delivery_late`, `docs_aggregate`, `is_upd_overdue`, `position_sum`, `procedure_sum`, `progress`, `overdue_pct`, `_parse_date`). New Pydantic schemas in `schemas/dashboard.py`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2, pytest + httpx TestClient.

**Design spec:** `docs/superpowers/specs/2026-06-27-phase8-dashboard-design.md` (authoritative for decisions R1–R10 and all formulas).

## Global Constraints

- **Python interpreter (Windows):** `python` in Git Bash is the Store stub. Use `PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`; run tests as `cd backend && "$PY" -m pytest ...`. Do NOT use `backend/.venv`.
- **Money = INTEGER kopecks** end-to-end; **dates = ISO `YYYY-MM-DD` strings**. The dashboard sends meter `amount` / table `contract_sum` as **kopecks** (FE formats with `money()`); the only BE-formatted money is inside attention `text` sentences (via `_fmt_money`).
- **Read-only:** `_user: User = Depends(require_password_changed)`. NO `require_action` — dashboard is identical for all roles; data is global (no `department` filter — matches every existing list endpoint).
- **No `write_audit`** on `/dashboard` (pure read). **No Alembic migration** — all columns exist since Phase 1/6.
- **Literal values (case-sensitive, CHECK-constrained):** `block ∈ {'zakupka','soprovozhdenie'}`; `status_postavki ∈ {'Новая','В производстве','В поставке','Частично поставлено','Поставлено','Отменена'}`; `status_zakup='Отменена'` = cancelled procedure (закупка); `pay_status ∈ {'await','paid'}`; delivery `status ∈ {'transit','done'}`.
- **«Completed» procedure** (Phase 6 R6) = `status_postavki='Поставлено'` AND ≥1 УПД AND all its УПД `paid`. Excluded from operational meters/flow/tables, but its УПД counted in financial meters (`upd_await`/`upd_overdue` are УПД-level, so a paid УПД on a completed proc simply isn't `await`).
- **`Отменена` excluded** from all operational counters; УПД of cancelled procedures excluded everywhere (filter `status_postavki IS NULL OR != 'Отменена'`, same as `payments_summary`).
- **seg-bar:** every meter `seg = {on: round(ratio*14) clamped 0..14, total: 14}` (concept canon).
- **TDD per task:** red → green → commit. Commit prefix `feat(dashboard):` (or `test(dashboard):`).
- After all tasks: full `pytest -q` green (no regressions), then **⏸ STOP** for user.

## File Structure

- **Create** `backend/app/schemas/dashboard.py` — all Pydantic DTOs for `/dashboard` (one responsibility: dashboard response shapes). Defined once in Task 1.
- **Create** `backend/app/routers/dashboard.py` — the `/dashboard` router (single `GET /dashboard`). Mirrors `payments.py` summary endpoint.
- **Create** `backend/tests/test_dashboard.py` — one test module (self-contained fixtures mirroring `tests/test_payments.py`).
- **Modify** `backend/app/calculations.py` — add `dashboard(db, today)` + helpers (`_load_dashboard_ctx`, `_dash_meters`, `_dash_flow`, `_dash_attention`, `_dash_feed`, `_dash_tables`, `is_procedure_completed`, `proc_sum`, `_fmt_money`) and constants.
- **Modify** `backend/app/main.py` — register the dashboard router.

Decomposition rationale: schemas + router skeleton + auth are foundational (Task 1); the aggregate is built section-by-section (meters/flow → attention → feed → tables) so each task is independently testable, with a shared context loaded once and read by thin formatters.

---

## Task 1: Schemas + router skeleton + `GET /dashboard` (stub) + auth

**Files:**
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/app/routers/dashboard.py`
- Modify: `backend/app/main.py:3` (import) and after `:13` (include router)
- Test: `backend/tests/test_dashboard.py`

**Interfaces:**
- Consumes: `app.calculations.dashboard` (stub in this task), `app.dependencies.require_password_changed`, `app.db.get_db`, `app.models.User`.
- Produces: `GET /dashboard` → `DashboardOut`; schemas `DashboardOut`, `MeterOut`, `SegBar`, `FlowStageOut`, `AttentionItemOut`, `FeedItemOut`, `TargetOut`, `AwaitingRowOut`, `ProcurementRowOut`, `SupportRowOut`, `CompactAwaitingOut`, `CompactProcurementOut`, `CompactSupportOut`, `DashboardTables` (all defined here).

- [ ] **Step 1: Write `backend/app/schemas/dashboard.py` (complete)**

```python
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
```

- [ ] **Step 2: Write `backend/app/routers/dashboard.py` (skeleton)**

```python
"""/dashboard router (Phase 8.1) — обзорный экран (одинаков для всех ролей).

Read-only: auth = require_password_changed (NO require_action). Data is global.
Spec: docs/14-page-dashboard.md, docs/32 §6. Decisions: docs/superpowers/specs/2026-06-27-phase8-dashboard-design.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import calculations as calc
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import User
from app.schemas.dashboard import DashboardOut


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> DashboardOut:
    data = calc.dashboard(db, calc.today_moscow())
    return DashboardOut(**data)
```

- [ ] **Step 3: Register the router in `backend/app/main.py`**

Change line 3 import to include `dashboard` (alphabetical, between `dict` and `payments`):

```python
from app.routers import auth, dashboard, dict, payments, procurement, requests, search, support, users
```

Add the include (after `app.include_router(procurement.router)`):

```python
app.include_router(dashboard.router)
```

- [ ] **Step 4: Add the `dashboard` stub to `backend/app/calculations.py`**

Append (after `payments_summary`) and add `"dashboard"` to `__all__`:

```python
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
```

- [ ] **Step 5: Write the failing tests in `backend/tests/test_dashboard.py`**

Create the file with self-contained fixtures (mirroring `tests/test_payments.py`) plus the Task 1 shape/auth tests. (Tasks 2–5 append tests to this same file; these fixtures/helpers stay in scope.)

```python
"""Tests for /dashboard router (Phase 8.1).

Pattern mirrors tests/test_payments.py: self-contained seeded fixtures,
client_admin (seeded admin, password changed), and role/flow helpers.
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


# --- fixtures (mirror test_payments.py) -----------------------------------------

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


def _to_zakupka(client, code, title, positions):
    """parent + positions → take-to-work. Returns procedure_id (block=zakupka)."""
    body = _create_request(client, code, title, positions)
    parent_id = body["id"]
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    return r.json()["procedure_id"]


def _to_support(client, code, title, positions):
    """parent + positions → take-to-work → price → 'На сделку' → to-support.
    Returns procedure_id (block=soprovozhdenie)."""
    proc_id = _to_zakupka(client, code, title, positions)
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


def _set_proc(db, proc_id, **fields):
    from app.models import Procedure
    db.query(Procedure).filter_by(id=proc_id).update(fields)
    db.commit()


def _set_delivery(db, delivery_id, **fields):
    from app.models import Delivery
    db.query(Delivery).filter_by(id=delivery_id).update(fields)
    db.commit()


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


# --- 8.1 Task 1: shape + auth ---------------------------------------------------

def test_dashboard_shape_empty(client_admin):
    r = client_admin.get("/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"meters", "flow", "attention", "feed", "tables"}
    assert set(body["tables"].keys()) == {"awaiting", "procurement", "support"}
    for k in ("awaiting", "procurement", "support"):
        assert set(body["tables"][k].keys()) == {"total", "items"}


def test_dashboard_unauth_401(client_seeded):
    # no login at all → 401
    assert client_seeded.get("/dashboard").status_code == 401


def test_dashboard_must_change_403(client_seeded):
    # seed admin BEFORE changing password → must_change_password=1 → 403
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    assert client_seeded.get("/dashboard").status_code == 403


def test_dashboard_ok_for_department_employee(client_seeded, db_seeded):
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/dashboard").status_code == 200
```

- [ ] **Step 6: Run tests to verify they fail (red)**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -v`
Expected: FAIL — `GET /dashboard` → 404 (router not registered until steps 2–3; the stub returns empty so once registered the shape test passes). Enforce red-first by running BEFORE steps 2–3.
Expected red output: `404 NOT FOUND` on `GET /dashboard`.

- [ ] **Step 7: Run tests to verify they pass (green)**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -v`
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/dashboard.py backend/app/routers/dashboard.py backend/app/main.py backend/app/calculations.py backend/tests/test_dashboard.py
git commit -m "feat(dashboard): GET /dashboard skeleton + schemas + auth (Phase 8.1 T1)"
```

---

## Task 2: `dashboard` meters (6) + flow (4) + shared context

**Files:**
- Modify: `backend/app/calculations.py` (replace the `dashboard` stub; add `_load_dashboard_ctx`, `_dash_meters`, `_dash_flow`, `is_procedure_completed`, `proc_sum`, `_fmt_money`)
- Test: `backend/tests/test_dashboard.py` (append)

**Interfaces:**
- Consumes: existing pure helpers `is_procedure_overdue`, `is_delivery_late`, `is_upd_overdue`, `position_sum`, `procedure_sum`, `_parse_date`; `or_` (already imported); models `ParentRequest, Procedure, ProcedurePosition, RequestedPosition, Tender, Delivery, UpdPayment`.
- Produces: `calc.dashboard(db, today)` now returns real `meters` (6) + `flow` (4) (attention/feed/tables still empty); `is_procedure_completed(proc, upds)`, `proc_sum(proc, positions)`.

**Authority for the math:** `docs/32 §6` + spec §4/§5. Key interpretations:
- `active_zakup` = procedures `block='zakupka'` AND `status_zakup≠'Отменена'`.
- `supp_procs` = procedures `block='soprovozhdenie'` AND `status_postavki≠'Отменена'` AND NOT `is_procedure_completed`.
- `active_total = len(active_zakup) + len(supp_procs)`.
- `on_time` = deliveries `status='done'` AND NOT `is_delivery_late(d, proc.srok_dd, today)`; `all_deliveries = len(all deliveries of active procs)`; `on_time_pct = round(on_time/all*100)` (0 if all=0).
- `overdue_procs` = subset of `supp_procs` where `is_procedure_overdue(srok_dd, status_postavki, today)`.
- УПД: `active` = `status_postavki IS NULL OR ≠'Отменена'` (manual УПД included); `await_upds` = `pay_status='await'`; `overdue_upds` = await AND `is_upd_overdue`.
- meter `amount` (kopecks) for money meters; `sub` (string) for text meters; `seg.on = clamp(round(ratio*14),0,14)`, `seg.total=14`.

- [ ] **Step 1: Add the failing tests (append to `backend/tests/test_dashboard.py`)**

```python
# --- 8.1 Task 2: meters + flow -------------------------------------------------

POS1 = [{"name": "x", "qty": 2.0, "unit": "шт", "price": 10000}]   # 2 * 100.00 = 20000


def _meters(client):
    return {m["key"]: m for m in client.get("/dashboard").json()["meters"]}


def _flow(client):
    return {s["key"]: s for s in client.get("/dashboard").json()["flow"]}


def test_meter_in_zakupka_count(client_admin):
    _to_zakupka(client_admin, "D-Z1", "z1", POS1)
    _to_zakupka(client_admin, "D-Z2", "z2", POS1)
    m = _meters(client_admin)
    assert m["in_zakupka"]["value"] == 2
    assert m["in_zakupka"]["sub"] == "процедур"
    assert m["in_zakupka"]["amount"] is None
    assert m["in_zakupka"]["seg"]["total"] == 14


def test_meter_in_zakupka_excludes_cancelled(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "D-ZX", "zx", POS1)
    # «Отменена» is a service value (PATCH→422) — set it directly on the row.
    _set_proc(db_seeded, pid, status_zakup="Отменена")
    assert _meters(client_admin)["in_zakupka"]["value"] == 0


def test_meter_in_support_count_and_contract_sum(client_admin, db_seeded):
    pid = _to_support(client_admin, "D-S1", "s1", POS1)
    _set_proc(db_seeded, pid, contract_sum=1500000)   # 15 000.00 ₽
    m = _meters(client_admin)
    assert m["in_support"]["value"] == 1
    assert m["in_support"]["amount"] == 1500000
    assert m["in_support"]["sub"] is None


def test_meter_in_support_excludes_completed(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-SC", "sc", POS1)
    # mark delivered + pay the УПД → completed
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")
    _set_proc(db_seeded, pid, status_postavki="Поставлено", srok_dd="2026-06-30")
    list_id = client_admin.get("/payments").json()["items"][0]["id"]
    client_admin.post(f"/payments/{list_id}/pay")
    # completed → not in operational counters
    assert _meters(client_admin)["in_support"]["value"] == 0


def test_meter_on_time_pct(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-OT", "ot", POS1)
    _set_proc(db_seeded, pid, srok_dd="2026-06-30")            # future deadline
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")  # before srok → on time
    m = _meters(client_admin)
    assert m["on_time_pct"]["value"] == 100
    assert m["on_time_pct"]["unit"] == "%"
    assert m["on_time_pct"]["sub"] == "1 / 1 поставок"


def test_meter_on_time_late_reduces_pct(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-OT2", "ot2", POS1)
    _set_proc(db_seeded, pid, srok_dd="2026-06-01")            # past deadline
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")  # after srok → late
    assert _meters(client_admin)["on_time_pct"]["value"] == 0  # 0 of 1 on time


def test_meter_overdue_count_and_sum(client_admin, db_seeded):
    pid = _to_support(client_admin, "D-OV", "ov", POS1)
    # position price 100.00 × 2 = 20000; srok in past, not delivered → overdue
    _set_proc(db_seeded, pid, srok_dd="2026-06-01", contract_sum=500000)
    m = _meters(client_admin)
    assert m["overdue"]["value"] == 1
    assert m["overdue"]["amount"] == 500000          # contract_sum used


def test_meter_upd_await_and_overdue(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-UA", "ua", POS1)  # await, amount 20000
    # make it overdue: past srok
    from app.models import UpdPayment
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": "2026-06-01"})
    db_seeded.commit()
    m = _meters(client_admin)
    assert m["upd_await"]["value"] == 1
    assert m["upd_await"]["amount"] == 20000
    assert m["upd_overdue"]["value"] == 1
    assert m["upd_overdue"]["amount"] == 20000


def test_meter_upd_excludes_cancelled_procedure(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "D-UC", "uc", POS1)
    _set_proc(db_seeded, pid, status_postavki="Отменена")
    m = _meters(client_admin)
    assert m["upd_await"]["value"] == 0
    assert m["upd_overdue"]["value"] == 0


def test_flow_four_stages_counts_and_routes(client_admin):
    _create_request(client_admin, "D-AW", "aw", POS1)          # awaiting (no tender)
    _to_zakupka(client_admin, "D-FZ", "fz", POS1)              # in zakupka
    f = _flow(client_admin)
    assert set(f.keys()) == {"awaiting", "procurement", "support", "payments"}
    assert f["awaiting"]["count"] == 1
    assert f["awaiting"]["route"] == "/komplektaciya"
    assert f["procurement"]["count"] == 1
    assert f["procurement"]["route"] == "/zakupka"
    assert f["support"]["count"] == 0
    assert f["support"]["route"] == "/soprovozhdenie"
    assert f["payments"]["count"] == 0
    assert f["payments"]["route"] == "/oplaty"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "meter or flow" -v`
Expected: FAIL — meters/flow empty (stub returns `[]`).

- [ ] **Step 3: Replace the `dashboard` stub and add helpers in `backend/app/calculations.py`**

Add `from collections import defaultdict` and `from types import SimpleNamespace` to the top imports. Then append (replace the Task-1 `dashboard` stub entirely):

```python
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
    int_part = f"{int(int_part):,}".replace(",", " ")
    frac = frac.rstrip("0")
    if frac:
        return f"{sign}{int_part},{frac} ₽"
    return f"{sign}{int_part} ₽"


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
    t = ctx.today
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


def dashboard(db, today: date) -> dict:
    """Дашборд (docs/14, docs/32 §6). Разделы attention/feed/tables — в Задачах 3–5."""
    ctx = _load_dashboard_ctx(db, today)
    return {
        "meters": _dash_meters(ctx),
        "flow": _dash_flow(ctx),
        "attention": [],                       # Task 3
        "feed": [],                            # Task 4
        "tables": {                            # Task 5
            "awaiting": {"total": 0, "items": []},
            "procurement": {"total": 0, "items": []},
            "support": {"total": 0, "items": []},
        },
    }
```

Add `"dashboard"`, `"is_procedure_completed"`, `"proc_sum"` to the `__all__` list in `calculations.py`.

- [ ] **Step 4: Run tests to verify they pass (green)**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "meter or flow" -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_dashboard.py
git commit -m "feat(dashboard): 6 meters + 4-stage flow + shared ctx (Phase 8.1 T2)"
```

---

## Task 3: «Требует внимания» (2-tier triggers)

**Files:**
- Modify: `backend/app/calculations.py` (add `_dash_attention`; wire into `dashboard`)
- Test: `backend/tests/test_dashboard.py` (append)

**Interfaces:**
- Consumes: `ctx` (from `_load_dashboard_ctx`); helpers `is_delivery_overdue`, `is_delivery_late`, `docs_aggregate`, `is_upd_overdue`, `_parse_date`, `_fmt_money`.
- Produces: `dashboard()["attention"]` = sorted list (errors first by `days` desc, then warnings); each `{id_label, severity, text, target}`.

**Triggers (spec §6):** 🔴 overdue delivery · 🔴 overdue payment · 🔴 missing docs (ТТН/М-15/УПД not received across all deliveries; procedure has ≥1 delivery) · 🟡 УПД without certificate (`await` delivery-УПД whose `delivery.doc_sert=0`). Errors precede warnings; FE renders top-20 + «и ещё N».

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 8.1 Task 3: attention (2-tier) --------------------------------------------

def _attention(client):
    return client.get("/dashboard").json()["attention"]


def test_attention_overdue_delivery_is_error(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "A-OD", "od", POS1)
    _set_proc(db_seeded, pid, srok_dd="2026-06-01")          # past, transit → overdue delivery
    items = _attention(client_admin)
    assert len(items) == 1
    it = items[0]
    assert it["severity"] == "error"
    assert "просрочена" in it["text"]
    assert it["target"] == {"kind": "procedure", "id": pid}


def test_attention_overdue_payment_is_error(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "A-OP", "op", POS1)
    from app.models import UpdPayment
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": "2026-06-01"})
    db_seeded.commit()
    # procedure has a no-docs delivery (missing-docs error) + this overdue-payment error;
    # filter to the payment item.
    items = [i for i in _attention(client_admin) if i["target"]["kind"] == "payment"]
    assert len(items) == 1
    assert items[0]["severity"] == "error"
    assert "к оплате" in items[0]["text"]


def test_attention_missing_documents_is_error(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "A-MD", "md", POS1)
    # delivery exists, no docs set → ttn/m15/upd all missing
    items = [i for i in _attention(client_admin) if i["target"] == {"kind": "procedure", "id": pid}]
    assert any(i["severity"] == "error" and "Документы не получены" in i["text"] for i in items)
    txt = next(i["text"] for i in items if "Документы не получены" in i["text"])
    assert "ТТН" in txt and "М-15" in txt and "УПД" in txt


def test_attention_no_delivery_no_missing_docs(client_admin):
    # procedure in support with NO delivery → must NOT trigger missing-docs
    pid = _to_support(client_admin, "A-ND", "nd", POS1)
    items = [i for i in _attention(client_admin) if i["target"] == {"kind": "procedure", "id": pid}]
    assert items == []


def test_attention_upd_without_certificate_is_warning(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "A-CERT", "cert", POS1)
    _set_proc(db_seeded, pid, srok_dd="2026-06-30")          # not overdue (future)
    # mark ТТН/М-15/УПД received (so missing-docs does NOT fire), leave sert=0 (warning)
    _set_delivery(db_seeded, d["id"], doc_ttn=1, doc_m15=1, doc_upd=1)
    items = _attention(client_admin)
    assert len(items) == 1
    assert items[0]["severity"] == "warning"
    assert "без сертификата" in items[0]["text"]
    assert items[0]["target"]["kind"] == "payment"


def test_attention_errors_before_warnings(client_admin, db_seeded):
    # warning: UPD without cert (future srok); mark ttn/m15/upd received so only cert fires
    p1, d1, _u1 = _delivery_upd(client_admin, "A-MIX1", "mix1", POS1)
    _set_proc(db_seeded, p1, srok_dd="2026-06-30")
    _set_delivery(db_seeded, d1["id"], doc_ttn=1, doc_m15=1, doc_upd=1)
    # error: overdue delivery
    p2, d2, _u2 = _delivery_upd(client_admin, "A-MIX2", "mix2", POS1)
    _set_proc(db_seeded, p2, srok_dd="2026-06-01")
    severities = [i["severity"] for i in _attention(client_admin)]
    # all errors appear before any warning
    if "warning" in severities:
        assert severities.index("warning") > max(
            idx for idx, s in enumerate(severities) if s == "error"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "attention" -v`
Expected: FAIL — `attention` is `[]`.

- [ ] **Step 3: Add `_dash_attention` to `backend/app/calculations.py` and wire it in**

Append the helper:

```python
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
```

In `dashboard()`, replace `"attention": [],` with:

```python
        "attention": _dash_attention(ctx),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "attention" -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_dashboard.py
git commit -m "feat(dashboard): «Требует внимания» 2-tier triggers (Phase 8.1 T3)"
```

---

## Task 4: «Лента событий» (last 20 audit_log)

**Files:**
- Modify: `backend/app/calculations.py` (add `_dash_feed`; wire into `dashboard`)
- Test: `backend/tests/test_dashboard.py` (append)

**Interfaces:**
- Consumes: `AuditLog`, `User` models; `_AUDIT_PHRASES`.
- Produces: `dashboard()["feed"]` = last 20 `audit_log` (newest first), each `{actor, action_label, entity_display?, target?, created_at}`. Polymorphic display: `parent`/`parent_request`→`ParentRequest.code`, `procedure`→`Procedure.proc`, `upd_payment`→`UpdPayment.upd`. `target.kind`: parent→`parent`, procedure→`procedure`, upd_payment→`payment`.

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 8.1 Task 4: feed (last 20 audit_log) -------------------------------------

def _feed(client):
    return client.get("/dashboard").json()["feed"]


def test_feed_has_recent_actions_with_actor_and_phrase(client_admin):
    _create_request(client_admin, "F-A1", "feed one", POS1)   # audit: parent/create
    feed = _feed(client_admin)
    assert feed, "feed should not be empty"
    top = feed[0]
    assert top["actor"]                       # non-empty actor
    assert top["action_label"]                # humanized phrase
    assert top["created_at"]                  # ISO timestamp
    # the most recent action was creating the request
    assert "заявку" in top["action_label"]
    assert top["entity_display"] == "F-A1"
    assert top["target"] == {"kind": "parent", "id": top["target"]["id"]}


def test_feed_newest_first(client_admin):
    _create_request(client_admin, "F-O1", "older", POS1)
    _create_request(client_admin, "F-O2", "newer", POS1)
    feed = _feed(client_admin)
    displays = [f["entity_display"] for f in feed if f["entity_display"] in ("F-O1", "F-O2")]
    assert displays[0] == "F-O2"              # newer first


def test_feed_payment_pay_phrase_and_target(client_admin):
    created = client_admin.post("/payments", json={"upd": "UPD-FP", "supplier": "S"}).json()
    client_admin.post(f"/payments/{created['id']}/pay")
    feed = _feed(client_admin)
    pay = next(f for f in feed if "оплату" in f["action_label"])
    assert pay["entity_display"] == "UPD-FP"
    assert pay["target"] == {"kind": "payment", "id": created["id"]}


def test_feed_capped_at_20(client_admin):
    for i in range(25):
        client_admin.post("/payments", json={"upd": f"UPD-CAP-{i}", "supplier": "S"})
    assert len(_feed(client_admin)) == 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "feed" -v`
Expected: FAIL — `feed` is `[]`.

- [ ] **Step 3: Add `_dash_feed` to `backend/app/calculations.py` and wire it in**

Append the helper:

```python
def _dash_feed(db) -> list:
    """«Лента событий» (spec §7): last 20 audit_log, newest first."""
    from app.models import (
        AuditLog, ParentRequest, Procedure, UpdPayment, User,
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
    proc_map = {pid: proc for pid, proc in
                db.query(Procedure.id, Procedure.proc)
                .filter(Procedure.id.in_(proc_ids)).all()} if proc_ids else {}
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
            display = proc_map.get(log.entity_id)
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
```

In `dashboard()`, replace `"feed": [],` with:

```python
        "feed": _dash_feed(db),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "feed" -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_dashboard.py
git commit -m "feat(dashboard): «Лента событий» last-20 audit feed (Phase 8.1 T4)"
```

---

## Task 5: Compact tables (awaiting / procurement / support) + full suite

**Files:**
- Modify: `backend/app/calculations.py` (add `_dash_tables`; wire into `dashboard`)
- Test: `backend/tests/test_dashboard.py` (append)

**Interfaces:**
- Consumes: `ctx`; helpers `proc_sum`, `progress`, `overdue_pct`.
- Produces: `dashboard()["tables"]` = `{awaiting:{total,items}, procurement:{total,items}, support:{total,items}}`; items = top-10 newest (`created_at desc`), `total` = true count.
  - awaiting rows (`ParentRequest` awaiting, no tender): `{id, code, title, mtr, srok, position_count, status}` → `/komplektaciya/:id`.
  - procurement rows (`block='zakupka'`, `status_zakup≠'Отменена'`): `{id, code, title, num(proc), supplier, position_count, status_zakup}` → `/zakupka/:id`.
  - support rows (`supp_procs`): `{id, code, title, num(proc), supplier, contract_sum, status_postavki, overdue_pct, delivered, total}` → `/soprovozhdenie/:id`.

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 8.1 Task 5: compact tables -----------------------------------------------

def _tables(client):
    return client.get("/dashboard").json()["tables"]


def test_table_awaiting(client_admin):
    _create_request(client_admin, "T-AW", "awaiting row", POS1)
    aw = _tables(client_admin)["awaiting"]
    assert aw["total"] == 1
    row = aw["items"][0]
    assert row["code"] == "T-AW"
    assert row["title"] == "awaiting row"
    assert row["position_count"] == 1
    assert row["status"] == "Ожидает"


def test_table_procurement(client_admin):
    pid = _to_zakupka(client_admin, "T-PR", "proc row", POS1)
    pr = _tables(client_admin)["procurement"]
    assert pr["total"] == 1
    row = pr["items"][0]
    assert row["id"] == pid
    assert row["code"] == "T-PR"
    assert row["position_count"] == 1


def test_table_support_contract_sum_progress(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "T-SU", "supp row", POS1)
    _set_proc(db_seeded, pid, contract_sum=750000)
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")
    su = _tables(client_admin)["support"]
    assert su["total"] == 1
    row = su["items"][0]
    assert row["id"] == pid
    assert row["contract_sum"] == 750000
    assert row["delivered"] == 1 and row["total"] == 1     # 1 of 1 positions delivered


def test_table_support_excludes_completed_and_cancelled(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "T-SC", "supp cx", POS1)
    _set_delivery(db_seeded, d["id"], status="done", date="2026-06-15")
    _set_proc(db_seeded, pid, status_postavki="Отменена")
    assert _tables(client_admin)["support"]["total"] == 0


def test_table_items_capped_at_10_total_true(client_admin):
    for i in range(12):
        _create_request(client_admin, f"T-CAP-{i:02d}", "cap", POS1)
    aw = _tables(client_admin)["awaiting"]
    assert aw["total"] == 12
    assert len(aw["items"]) == 10
    # newest first → T-CAP-11 is the first item
    assert aw["items"][0]["code"] == "T-CAP-11"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "table" -v`
Expected: FAIL — tables are empty stubs.

- [ ] **Step 3: Add `_dash_tables` to `backend/app/calculations.py` and wire it in**

Append the helper:

```python
def _dash_tables(db, ctx) -> dict:
    """Compact tables (spec §8): top-10 newest, true total."""
    from app.models import ParentRequest, ProcedurePosition, RequestedPosition, Tender

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
    pr_procs = sorted(ctx.active_zakup, key=lambda p: p.created_at, reverse=True)[:10]
    pr_pos = {pid: len(ctx.positions_by_proc.get(pid, [])) for pid in [p.id for p in pr_procs]}
    procurement_items = [{
        "id": p.id,
        "code": ctx.parent_map.get(p.id, {}).get("code"),
        "title": ctx.parent_map.get(p.id, {}).get("title"),
        "num": p.proc, "supplier": p.supplier,
        "position_count": pr_pos.get(p.id, 0), "status_zakup": p.status_zakup,
    } for p in pr_procs]

    # --- support (supp_procs) ---
    su_procs = sorted(ctx.supp_procs, key=lambda p: p.created_at, reverse=True)[:10]
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
```

`_dash_tables` needs `db` for the awaiting-parents query, so pass it explicitly. The final `dashboard()` is:

```python
def dashboard(db, today: date) -> dict:
    ctx = _load_dashboard_ctx(db, today)
    return {
        "meters": _dash_meters(ctx),
        "flow": _dash_flow(ctx),
        "attention": _dash_attention(ctx),
        "feed": _dash_feed(db),
        "tables": _dash_tables(db, ctx),
    }
```

Also ensure `func` is imported in `calculations.py` (add `from sqlalchemy import func` to the top imports — `or_` is already there).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_dashboard.py -k "table" -v`
Expected: 5 passed.

- [ ] **Step 5: Run the FULL backend suite (no regressions)**

Run: `cd backend && "$PY" -m pytest -q`
Expected: all green (previous total + new test_dashboard tests, 0 failures).

- [ ] **Step 6: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_dashboard.py
git commit -m "feat(dashboard): compact tables awaiting/procurement/support (Phase 8.1 T5)"
```

---

## ⏸ STOP — Phase 8.1 verification (before Frontend 8.2)

- [ ] `cd backend && "$PY" -m pytest -q` → all green, 0 failures.
- [ ] Spot-check via TestClient (or curl against dev server on :8000, logged in as admin):
  - `GET /dashboard` → `{meters[6], flow[4], attention[], feed[], tables{...}}`.
  - Hand-verify one meter (e.g. `in_zakupka` count) against `32 §6` on a small dev-DB slice.
  - «Требует внимания» contains expected triggers; «Лента событий» newest-first; compact tables top-10 + true totals.
- [ ] **Wait for user confirmation before Frontend 8.2.**

🔎 After Frontend 8.2 (next plan): ui-checker on the «Дашборд» page.
