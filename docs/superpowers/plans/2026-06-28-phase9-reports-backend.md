# Phase 9 «Отчёты + экспорт» — Backend 9.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the read-only reports backend — `GET /reports` (filter options) + `GET /reports/{type}` (4 report types as a generic snapshot) + `GET /reports/{type}/export` (Excel/PDF/CSV) — gated to Руководитель/Админ/Куратор, per `docs/15`, `docs/31 §6`, `docs/32 §8`.

**Architecture:** One new FastAPI router `routers/reports.py` (prefix `/reports`, read-only, auth = `require_action("reports","view")`) over existing tables (no migration). Report aggregates live in `calculations.py` as 4 builders `report_time/sums/late/people(db, today, flt)` over a shared `_load_report_ctx(db, today, flt)` (mirrors `_load_dashboard_ctx`), returning a **generic snapshot** `{type,title,period,kpis,sections}`. One new `export.py` renders the same snapshot to Excel (openpyxl) / PDF (reportlab + registry-resolved TTF for Cyrillic) / CSV (stdlib + UTF-8 BOM). New Pydantic schemas in `schemas/reports.py`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic v2, **openpyxl** + **reportlab** (NEW deps), pytest + httpx TestClient.

**Design spec:** `docs/superpowers/specs/2026-06-28-phase9-reports-design.md` (authoritative for decisions R1–R12, report contents, the snapshot/cell contract).

## Global Constraints

- **Python interpreter (Windows):** `python` in Git Bash is the Store stub. Use `PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`; run tests as `cd backend && "$PY" -m pytest ...`. Do NOT use `backend/.venv`.
- **Money = INTEGER kopecks**; **dates = ISO `YYYY-MM-DD`**. In the **snapshot**, all money/date **cells are pre-formatted strings** (`_fmt_money` → «1 500 ₽»; `_fmt_date` → «ДД.ММ.ГГ») so JSON view and file export render identically.
- **Read-only:** every route depends on `require_action("reports","view")` (= Руководитель/Админ/Куратор; employee → 403). Data is global (no block scope — Куратор sees all). **No `write_audit`** (pure read). **No Alembic migration.**
- **`Отменена` excluded everywhere** (procedures `status_zakup='Отменена'` and `status_postavki='Отменена'`; УПД of cancelled procedures excluded via `status_postavki IS NULL OR != 'Отменена'`).
- **Period anchor = `parent_request.zagruzka`** (R3), `[from,to]` inclusive. Procedures join to parent via `tender`; awaiting parents filter on their own `zagruzka`.
- **`block ∈ {'zakupka','soprovozhdenie'}`.** Completed procedure (Phase 6 R6) = `status_postavki='Поставлено'` AND ≥1 УПД AND all paid → excluded from `time` (operational), **included** in `sums`/financial (R8).
- **Stuck flag = days ≥ 3** (R4, `32 §8.1`). day-pill color is independent: `≥14`→bad, `≥10`→warn (visual canon only).
- **TDD per task:** red → green → commit. Commit prefix `feat(reports):` (or `test(reports):`/`chore(reports):`).
- After all tasks: full `pytest -q` green (no regressions), then **⏸ STOP** for user.

## File Structure

- **Create** `backend/app/schemas/reports.py` — Pydantic DTOs for the generic snapshot + filter options. Defined in Task 1.
- **Create** `backend/app/routers/reports.py` — the `/reports` router (3 endpoints). Mirrors `dashboard.py` (thin) + `payments.py` (validation pattern).
- **Create** `backend/app/export.py` — `render_csv/render_excel/render_pdf(snapshot)` + `_register_fonts()`. Task 7.
- **Create** `backend/app/fonts/` — `DejaVuSans.ttf`, `DejaVuSans-Bold.ttf` (optional bundled Cyrillic TTFs; registry falls back to Windows `arial.ttf`).
- **Create** `backend/tests/test_reports.py` — one test module, self-contained fixtures (mirror `tests/test_dashboard.py`).
- **Modify** `backend/app/calculations.py` — add `_resolve_period`, `_load_report_ctx`, `_fmt_date`, cell helpers (`_claim/_stage/_days/_money/_pct/_date_late/_kpi/_snapshot`), and 4 builders `report_time/sums/late/people`.
- **Modify** `backend/app/main.py` — register the reports router.
- **Modify** `backend/pyproject.toml` — add `openpyxl`, `reportlab`.

Decomposition: Task 1 = deps + fonts + schemas + router skeleton (2 of 3 endpoints) + auth/validation + shared fixtures; Task 2 = period resolution + shared context + real `GET /reports` filters; Tasks 3–6 = the 4 builders one at a time; Task 7 = export (3 formats + the 3rd route). Each task is independently testable.

---

## Task 1: deps + fonts + schemas + router skeleton + auth/validation + fixtures

**Files:**
- Modify: `backend/pyproject.toml` (add deps)
- Create: `backend/app/fonts/.gitkeep` (dir marker; real TTFs added in Task 7)
- Create: `backend/app/schemas/reports.py`
- Create: `backend/app/routers/reports.py`
- Modify: `backend/app/main.py` (register router)
- Modify: `backend/app/calculations.py` (stub builders + `_fmt_date`)
- Test: `backend/tests/test_reports.py`

**Interfaces:**
- Consumes: `app.dependencies.require_password_changed` (via `permissions.require_action`), `app.db.get_db`, `app.models.User`.
- Produces: `GET /reports` → `FiltersOut` (stub `{mtr:[],supplier:[],author:[]}` in T1, real in T2); `GET /reports/{type}` → `ReportOut` (builders stubbed → empty snapshot in T1); unknown `type` → 404; `period=custom` bad range → 422; auth 401/403. Schemas: `ReportOut, PeriodInfo, Kpi, Column, Section, CellObj, FiltersOut`.

- [ ] **Step 1: Add dependencies to `backend/pyproject.toml`**

In the `dependencies` list, add (alphabetical — after `pydantic>=2`, before `python-multipart`):

```toml
    "openpyxl",
    "reportlab",
```

- [ ] **Step 2: Install the new deps**

Run: `cd backend && "$PY" -m pip install openpyxl reportlab`
Expected: both install successfully (`Successfully installed openpyxl-... reportlab-...`).

- [ ] **Step 3: Create the fonts directory marker**

Create `backend/app/fonts/.gitkeep` (empty file) so the dir exists; real TTFs land in Task 7.

```bash
mkdir -p backend/app/fonts && touch backend/app/fonts/.gitkeep
```

- [ ] **Step 4: Write `backend/app/schemas/reports.py` (complete)**

```python
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
```

- [ ] **Step 5: Add `_fmt_date` + stub builders to `backend/app/calculations.py`**

Append after `_fmt_money` (near the dashboard helpers) the date formatter:

```python
def _fmt_date(value) -> str:
    """ISO 'YYYY-MM-DD' → 'ДД.ММ.ГГ'. None/invalid → ''."""
    d = _parse_date(value)
    if d is None:
        return ""
    return f"{d.day:02d}.{d.month:02d}.{str(d.year)[2:]}"
```

Append the 4 builder stubs (after `dashboard`) and add their names + `_fmt_date` to `__all__`:

```python
# ---------------------------------------------------------------------------
# Reports (Phase 9.1) — docs/15, docs/32 §8
# ---------------------------------------------------------------------------

def report_time(db, today: date, flt: dict) -> dict:
    """Время на этапе / зависания. Stub — real in Task 3."""
    return {"type": "time", "title": "Время на этапе и зависания",
            "period": None, "kpis": [], "sections": []}


def report_sums(db, today: date, flt: dict) -> dict:
    """Суммы по этапам и поставщикам. Stub — real in Task 4."""
    return {"type": "sums", "title": "Суммы по этапам и поставщикам",
            "period": None, "kpis": [], "sections": []}


def report_late(db, today: date, flt: dict) -> dict:
    """Просрочки: поставки и оплаты. Stub — real in Task 5."""
    return {"type": "late", "title": "Просрочки: поставки и оплаты",
            "period": None, "kpis": [], "sections": []}


def report_people(db, today: date, flt: dict) -> dict:
    """Сводка по составителям/отделам. Stub — real in Task 6."""
    return {"type": "people", "title": "Сводка по составителям/отделам",
            "period": None, "kpis": [], "sections": []}
```

- [ ] **Step 6: Write `backend/app/routers/reports.py` (skeleton with validation)**

```python
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
    # Real distinct options land in Task 2; stub returns empty lists.
    return FiltersOut(mtr=[], supplier=[], author=[])


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
```

- [ ] **Step 7: Register the router in `backend/app/main.py`**

In the routers import (line ~3), add `reports` (alphabetical, after `procurement`):

```python
from app.routers import auth, dashboard, dict, payments, procurement, reports, requests, search, support, users
```

After `app.include_router(procurement.router)` add:

```python
app.include_router(reports.router)
```

- [ ] **Step 8: Write `backend/tests/test_reports.py` (fixtures + Task 1 tests)**

```python
"""Tests for /reports router (Phase 9.1). Mirrors tests/test_dashboard.py."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.calculations import today_moscow
from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"
TODAY = today_moscow()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def last_month_date() -> str:
    # a date firmly in the previous calendar month (robust regardless of today's day)
    first_this = TODAY.replace(day=1)
    return (first_this - timedelta(days=5)).isoformat()


# --- fixtures (mirror test_dashboard.py) ---------------------------------------

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

POS = [{"name": "x", "qty": 2.0, "unit": "шт", "price": 10000}]   # 2 * 100.00 = 20000 kop


def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_zakupka(client, code, title, positions):
    body = _create_request(client, code, title, positions)
    r = client.post(f"/requests/{body['id']}/take-to-work")
    assert r.status_code == 200, r.text
    return r.json()["procedure_id"]


def _to_support(client, code, title, positions):
    proc_id = _to_zakupka(client, code, title, positions)
    for src, pp in zip(positions, client.get(f"/procedures/{proc_id}").json()["positions"]):
        if src.get("price") is not None:
            client.patch(f"/procedures/{proc_id}/positions/{pp['id']}", json={"price": src["price"]})
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r = client.post(f"/procedures/{proc_id}/to-support")
    assert r.status_code == 200, r.text
    return proc_id


def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def _delivery_upd(client, code, title, positions):
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


def _make_role_user(db, email, department, is_curator=False, global_role=None):
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name=email.split("@")[0], account_type="department" if department else "global",
        department=department, is_curator=1 if is_curator else 0, global_role=global_role,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login_as(client, email, password="userpass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


# --- 9.1 Task 1: shape / auth / validation -------------------------------------

def test_report_shape_and_keys(client_admin):
    r = client_admin.get("/reports/time")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"type", "title", "period", "kpis", "sections"}
    assert body["type"] == "time"


def test_report_unknown_type_404(client_admin):
    assert client_admin.get("/reports/bogus").status_code == 404


def test_report_unauth_401(client_seeded):
    assert client_seeded.get("/reports/time").status_code == 401


def test_report_must_change_403(client_seeded):
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    assert client_seeded.get("/reports/time").status_code == 403


def test_report_employee_forbidden_403(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "kompl_emp@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 403


def test_report_curator_ok(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "kompl_cur@crm.local", "Комплектация", is_curator=True)
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 200


def test_report_rukovoditel_ok(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "ruk@crm.local", None, global_role="Руководитель")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 200


def test_report_custom_period_validation_422(client_admin):
    # custom without range
    assert client_admin.get("/reports/time?period=custom").status_code == 422
    # custom inverted
    q = f"?period=custom&date_from={days_ago(1)}&date_to={days_ago(5)}"
    assert client_admin.get("/reports/time" + q).status_code == 422


def test_report_custom_period_ok(client_admin):
    q = f"?period=custom&date_from={days_ago(10)}&date_to={days_ago(0)}"
    r = client_admin.get("/reports/time" + q)
    assert r.status_code == 200
    assert r.json()["period"]["key"] == "custom"


def test_report_unknown_period_422(client_admin):
    assert client_admin.get("/reports/time?period=bogus").status_code == 422


def test_filters_shape(client_admin):
    r = client_admin.get("/reports")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"mtr", "supplier", "author"}
```

- [ ] **Step 9: Run tests to verify they fail (red)**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -v`
Expected: FAIL — `GET /reports/time` → 404 (router not registered until steps 6–7). Run BEFORE steps 6–7 to see red.

- [ ] **Step 10: Run tests to verify they pass (green)**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -v`
Expected: 11 passed.

- [ ] **Step 11: Commit**

```bash
git add backend/pyproject.toml backend/app/fonts/.gitkeep backend/app/schemas/reports.py backend/app/routers/reports.py backend/app/main.py backend/app/calculations.py backend/tests/test_reports.py
git commit -m "feat(reports): schemas + router skeleton + auth/validation + deps (Phase 9.1 T1)"
```

---

## Task 2: period resolution + shared report context + real `GET /reports` filters

**Files:**
- Modify: `backend/app/calculations.py` (add `_resolve_period`, `_load_report_ctx`, `_fmt_date` already in place)
- Modify: `backend/app/routers/reports.py` (real `get_filters`)
- Test: `backend/tests/test_reports.py` (append)

**Interfaces:**
- Consumes: models `Delivery, ParentRequest, Procedure, ProcedurePosition, Tender, UpdPayment, User`; existing `is_procedure_completed`, `_parse_date`, `or_`.
- Produces: `_resolve_period(flt, today) -> (from_d|None, to_d|None, period_info|None)`; `_load_report_ctx(db, today, flt)` → SimpleNamespace with `today, period_info, from_d, to_d, has_period, procs, parent_by_proc, deliveries_by_proc, positions_by_proc, upds, upds_by_proc, completed_proc_ids, delivery_proc, awaiting_parents`. `GET /reports` returns real distinct mtr/supplier/author.

**Authority:** spec R3 (anchor `zagruzka`), R6 (manual-УПД excluded when period active), R8 (`Отменена` excluded). Filter semantics: `mtr` matches `proc.mtr or parent.mtr`; `supplier` matches `proc.supplier`; `author` matches `parent.sostavitel`; period matches `parent.zagruzka` (inclusive).

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 9.1 Task 2: period + ctx + filters ---------------------------------------

from app import calculations as calc


def test_resolve_period_month():
    f, t, info = calc._resolve_period({"period": "month"}, TODAY)
    assert f == TODAY.replace(day=1)
    assert t == TODAY
    assert info["key"] == "month" and info["label"] == "Текущий месяц"


def test_resolve_period_quarter():
    f, t, info = calc._resolve_period({"period": "quarter"}, TODAY)
    qm = ((TODAY.month - 1) // 3) * 3 + 1
    from datetime import date
    assert f == date(TODAY.year, qm, 1)


def test_resolve_period_year():
    f, t, info = calc._resolve_period({"period": "year"}, TODAY)
    from datetime import date
    assert f == date(TODAY.year, 1, 1)
    assert info["label"] == "С начала года"


def test_resolve_period_custom():
    f, t, info = calc._resolve_period(
        {"period": "custom", "date_from": days_ago(10), "date_to": days_ago(2)}, TODAY)
    assert info["key"] == "custom"
    assert info["from"] == days_ago(10)


def test_resolve_period_none():
    f, t, info = calc._resolve_period({}, TODAY)
    assert f is None and t is None and info is None


def test_ctx_period_filters_procedures_by_zagruzka(client_admin, db_seeded):
    from app.models import ParentRequest, Procedure, Tender
    p_in = _to_zakupka(client_admin, "P-IN", "in", POS)
    p_out = _to_zakupka(client_admin, "P-OUT", "out", POS)
    # move p_out's parent zagruzka to a date firmly in the previous month
    out_par_id = (db_seeded.query(Tender)
                  .join(Procedure, Procedure.tender_id == Tender.id)
                  .filter(Procedure.id == p_out).first()).parent_id
    db_seeded.query(ParentRequest).filter_by(id=out_par_id).update({"zagruzka": last_month_date()})
    db_seeded.commit()
    ctx = calc._load_report_ctx(db_seeded, TODAY, {"period": "month"})
    ids = [p.id for p in ctx.procs]
    assert p_in in ids and p_out not in ids


def test_ctx_filters_mtr_supplier_author(client_admin, db_seeded):
    _to_zakupka(client_admin, "F-MTR", "mtr", [{"name": "x", "qty": 1, "unit": "шт", "price": 100}])
    # filter by supplier that doesn't exist → empty
    ctx = calc._load_report_ctx(db_seeded, TODAY, {"supplier": "Никто"})
    assert ctx.procs == []


def test_filters_endpoint_returns_distinct(client_admin, db_seeded):
    _to_zakupka(client_admin, "F-S1", "s1", POS)               # supplier unset here
    proc_id = _to_support(client_admin, "F-S2", "s2", POS)
    _set_proc(db_seeded, proc_id, supplier="ООО Ромашка")
    r = client_admin.get("/reports")
    body = r.json()
    assert "ООО Ромашка" in body["supplier"]


def test_filters_endpoint_forbidden_employee(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "k2@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports").status_code == 403
```

Note: `calc.Procedure` is used for brevity — but `_load_report_ctx` imports models locally. In tests, reference models via `from app.models import Procedure, Tender, ParentRequest`. (The `calc.Procedure` reference in `test_ctx_period_filters_procedures_by_zagruzka` above is illustrative — replace those two lines with the clean direct-query version shown at the end of that test.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "resolve_period or ctx_ or filters_endpoint" -v`
Expected: FAIL — `_resolve_period`/`_load_report_ctx` undefined; `get_filters` returns empty.

- [ ] **Step 3: Add `_resolve_period` + `_load_report_ctx` to `backend/app/calculations.py`**

Append after the report stubs (Task 1) — these are shared infra used by Tasks 3–6:

```python
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
```

(`defaultdict`, `SimpleNamespace`, `or_` are already imported in `calculations.py`.)

- [ ] **Step 4: Implement the real `get_filters` in `backend/app/routers/reports.py`**

Replace the stub body of `get_filters`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "resolve_period or ctx_ or filters_endpoint" -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/calculations.py backend/app/routers/reports.py backend/tests/test_reports.py
git commit -m "feat(reports): period resolution + shared context + filters endpoint (Phase 9.1 T2)"
```

---

## Task 3: `report_time` — время на этапе / зависания

**Files:**
- Modify: `backend/app/calculations.py` (replace `report_time` stub; add cell/format helpers `_claim/_stage/_days/_kpi/_snapshot`)
- Test: `backend/tests/test_reports.py` (append)

**Interfaces:**
- Consumes: `_load_report_ctx`, `_fmt_money`, `_fmt_date`, `_parse_date`, `is_procedure_completed`.
- Produces: real `report_time(db, today, flt)` → snapshot with KPIs (Заявок в работе / Зависли ≥3 дн. / Ср. время на этапе) + 1 section (Заявка · № · Поставщик · Этап · Дней · Срок поставки). Rows = active procedures (not completed, not Отменена, has `block_entered_at`) + awaiting parents. Shared cell helpers used by Tasks 4–6 too.

**Authority:** spec R4 (procedures + awaiting; stuck ≥3; day-pill ≥10/≥14), R8 (completed excluded).

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 9.1 Task 3: report_time ---------------------------------------------------

def _report(client, type_="time", **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return client.get(f"/reports/{type_}" + (f"?{qs}" if qs else "")).json()


def test_time_includes_procedure_with_days(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "T-Z1", "z1", POS)
    _set_proc(db_seeded, pid, block_entered_at=days_ago(12))
    snap = _report(client_admin, "time")
    rows = snap["sections"][0]["rows"]
    assert any(r[0].get("code") == "T-Z1" for r in rows)
    day_cell = next(r[4] for r in rows if r[0].get("code") == "T-Z1")
    assert day_cell["text"] == "12 дн." and day_cell["level"] == "warn"
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Заявок в работе"] == "1"
    assert kpi["Зависли ≥3 дн."] == "1"


def test_time_excludes_completed_procedure(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "T-CM", "cm", POS)
    _set_delivery(db_seeded, d["id"], status="done", date=days_ago(1))
    _set_proc(db_seeded, pid, status_postavki="Поставлено", srok_dd=days_ago(-30), block_entered_at=days_ago(5))
    pay_id = client_admin.get("/payments").json()["items"][0]["id"]
    client_admin.post(f"/payments/{pay_id}/pay")            # → completed
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    assert not any(r[0].get("code") == "T-CM" for r in rows)


def test_time_excludes_cancelled(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "T-CA", "ca", POS)
    _set_proc(db_seeded, pid, status_zakup="Отменена", block_entered_at=days_ago(2))
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    assert not any(r[0].get("code") == "T-CA" for r in rows)


def test_time_includes_awaiting_parent_komplektaciya(client_admin):
    _create_request(client_admin, "T-AW", "awaiting", POS)   # no tender → awaiting
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    aw = [r for r in rows if r[0].get("code") == "T-AW"]
    assert aw and aw[0][3]["text"] == "Комплектация"          # stage cell


def test_time_avg_and_sort_desc(client_admin, db_seeded):
    p1 = _to_zakupka(client_admin, "T-A1", "a1", POS); _set_proc(db_seeded, p1, block_entered_at=days_ago(2))
    p2 = _to_zakupka(client_admin, "T-A2", "a2", POS); _set_proc(db_seeded, p2, block_entered_at=days_ago(8))
    snap = _report(client_admin, "time")
    days_list = [r[4]["text"] for r in snap["sections"][0]["rows"]]
    assert days_list[0] == "8 дн."                            # desc
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Ср. время на этапе"] == "5 дн."               # (8+2)/2


def test_time_no_block_entered_at_excluded(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "T-NB", "nb", POS)
    _set_proc(db_seeded, pid, block_entered_at=None)
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    assert not any(r[0].get("code") == "T-NB" for r in rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "time_" -v`
Expected: FAIL — `report_time` returns empty sections.

- [ ] **Step 3: Replace the `report_time` stub + add shared cell helpers in `backend/app/calculations.py`**

Add the shared cell/format helpers (used by all 4 builders) just above the `report_time` stub, then replace the stub:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "time_" -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_reports.py
git commit -m "feat(reports): report_time — время на этапе + зависания (Phase 9.1 T3)"
```

---

## Task 4: `report_sums` — суммы по этапам и поставщикам

**Files:**
- Modify: `backend/app/calculations.py` (replace `report_sums` stub)
- Test: `backend/tests/test_reports.py` (append)

**Interfaces:**
- Consumes: `_load_report_ctx`, `proc_sum`, cell helpers.
- Produces: real `report_sums` → KPIs (Всего по договорам / В сопровождении / В оплате) + section 1 «По этапам» (2 rows: Закупки/Сопровождение + Итого footer) + section 2 «По поставщикам». Universe = procedures with `status_zakup≠Отменена` AND `status_postavki≠Отменена` (**completed included**, R5/R8). «В оплате» = Σ `amount` of `await` УПД (active).

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 9.1 Task 4: report_sums ---------------------------------------------------

def test_sums_stage_totals_and_footer(client_admin, db_seeded):
    p1 = _to_zakupka(client_admin, "S-Z1", "z1", POS)
    _set_proc(db_seeded, p1, contract_sum=200000)                  # 2 000 ₽ (block zakupka)
    p2 = _to_support(client_admin, "S-S1", "s1", POS)
    _set_proc(db_seeded, p2, contract_sum=500000)                  # 5 000 ₽ (block support)
    snap = _report(client_admin, "sums")
    sec1 = snap["sections"][0]
    rows = {r[0]["text"]: r for r in sec1["rows"]}
    assert rows["В закупке"][2]["text"] == _fmt_money_expected(200000)
    assert rows["В сопровождении"][2]["text"] == _fmt_money_expected(500000)
    assert sec1["footer"][2]["text"] == _fmt_money_expected(700000)


def _fmt_money_expected(kop):
    # mirror calculations._fmt_money for assertions
    rub = kop / 100
    s = f"{int(rub):,}".replace(",", " ")
    return f"{s} ₽"


def test_sums_supplier_section(client_admin, db_seeded):
    p1 = _to_support(client_admin, "S-P1", "p1", POS); _set_proc(db_seeded, p1, supplier="Альфа", contract_sum=100000)
    p2 = _to_support(client_admin, "S-P2", "p2", POS); _set_proc(db_seeded, p2, supplier="Альфа", contract_sum=200000)
    p3 = _to_support(client_admin, "S-P3", "p3", POS); _set_proc(db_seeded, p3, supplier="Бета", contract_sum=50000)
    snap = _report(client_admin, "sums")
    sec2 = next(s for s in snap["sections"] if s.get("title") == "По поставщикам")
    by = {r[0]: r for r in sec2["rows"]}
    assert by["Альфа"][1] == "2" and by["Бета"][1] == "1"
    # sorted desc by sum → Альфа first
    assert sec2["rows"][0][0] == "Альфа"


def test_sums_kpi_v_oplate(client_admin, db_seeded):
    _delivery_upd(client_admin, "S-UP", "up", POS)   # 1 await УПД, amount = Σ delivery pos = 20000
    snap = _report(client_admin, "sums")
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["В оплате"] == _fmt_money_expected(20000)


def test_sums_excludes_cancelled_includes_completed(client_admin, db_seeded):
    p_c = _to_support(client_admin, "S-CM", "cm", POS); _set_proc(db_seeded, p_c, contract_sum=300000, status_postavki="Поставлено")
    p_x = _to_zakupka(client_admin, "S-CA", "ca", POS); _set_proc(db_seeded, p_x, status_zakup="Отменена")
    snap = _report(client_admin, "sums")
    sec1 = snap["sections"][0]
    # completed (Поставлено) counted in support; cancelled excluded
    sup_row = next(r for r in sec1["rows"] if r[0]["text"] == "В сопровождении")
    assert int(sup_row[1]) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "sums_" -v`
Expected: FAIL — `report_sums` returns empty sections.

- [ ] **Step 3: Replace the `report_sums` stub in `backend/app/calculations.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "sums_" -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_reports.py
git commit -m "feat(reports): report_sums — суммы по этапам и поставщикам (Phase 9.1 T4)"
```

---

## Task 5: `report_late` — просрочки: поставки и оплаты

**Files:**
- Modify: `backend/app/calculations.py` (replace `report_late` stub)
- Test: `backend/tests/test_reports.py` (append)

**Interfaces:**
- Consumes: `_load_report_ctx`, `is_delivery_overdue`, `is_delivery_late`, `is_upd_overdue`, `overdue_pct`, cell helpers.
- Produces: real `report_late` → KPIs (Просроч. поставок / Просроч. оплат) + section «Поставки» (Заявка · № · Поставщик · Поставка · % позиций · Срок ДД) + section «Оплаты» (УПД · Заявка · Поставщик · Сумма). Empty section → one `note` row «нет». УПД claim resolved: delivery-УПД → (parent code, proc); manual-УПД → plain `request_label` string.

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 9.1 Task 5: report_late ---------------------------------------------------

def test_late_overdue_delivery(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "L-OD", "od", POS)
    _set_proc(db_seeded, pid, srok_dd=days_ago(5))               # past, transit → overdue
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Поставки")
    assert any(r[0].get("code") == "L-OD" for r in sec["rows"])
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Просроч. поставок"] == "1"


def test_late_payment_overdue(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "L-OP", "op", POS)
    from app.models import UpdPayment
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": days_ago(3)})
    db_seeded.commit()
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    assert any(r[0] == "UPD-L-OP" for r in sec["rows"])
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Просроч. оплат"] == "1"


def test_late_excludes_cancelled_procedure(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "L-CA", "ca", POS)
    _set_proc(db_seeded, pid, srok_dd=days_ago(5), status_postavki="Отменена")
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Поставки")
    assert all(r[0].get("code") != "L-CA" for r in sec["rows"])


def test_late_empty_section_shows_note(client_admin):
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Поставки")
    assert sec["rows"] and sec["rows"][0][0]["text"] == "нет"


def test_late_manual_upd_excluded_when_period(client_admin):
    client_admin.post("/payments", json={"upd": "UPD-MAN", "supplier": "S", "srok": days_ago(5), "amount": 10000})
    snap = _report(client_admin, "late", period="month")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    assert all("UPD-MAN" not in str(r) for r in sec["rows"])


def test_late_manual_upd_included_no_period(client_admin):
    client_admin.post("/payments", json={"upd": "UPD-MAN2", "supplier": "S", "srok": days_ago(5), "amount": 10000})
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    assert any(r[0] == "UPD-MAN2" for r in sec["rows"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "late_" -v`
Expected: FAIL — `report_late` returns empty sections.

- [ ] **Step 3: Replace the `report_late` stub in `backend/app/calculations.py`**

```python
def _empty_note_row(ncols):
    return [{"kind": "note", "text": "нет"}] + [""] * (ncols - 1)


def _upd_claim(u, ctx):
    """delivery-УПД → (code, proc) claim; manual-УПД → request_label plain string."""
    if u.delivery_id is not None:
        pid = ctx.delivery_proc.get(u.delivery_id)
        if pid is not None:
            par = ctx.parent_by_proc.get(pid, {})
            proc = next((p for p in ctx.procs if p.id == pid), None)
            return _claim(par.get("code"), proc.proc if proc and proc.proc else par.get("title"))
    return u.request_label or "—"


def report_late(db, today: date, flt: dict) -> dict:
    """Просрочки: поставки и оплаты (spec R6/R8)."""
    ctx = _load_report_ctx(db, today, flt)
    today = ctx.today

    late_dels = []  # (proc, delivery, is_late)
    for p in ctx.procs:
        if p.status_postavki == "Отменена":
            continue
        for d in ctx.deliveries_by_proc.get(p.id, []):
            ov = is_delivery_overdue(d, p.srok_dd, today)
            lt = is_delivery_late(d, p.srok_dd, today)
            if ov or lt:
                late_dels.append((p, d, lt))

    late_upds = [u for u in ctx.upds if is_upd_overdue(u, today)]

    kpis = [
        _kpi("Просроч. поставок", str(len(late_dels)), "--late"),
        _kpi("Просроч. оплат", str(len(late_upds)), "--late"),
    ]

    cols_d = [
        {"key": "claim", "label": "Заявка", "kind": "claim", "align": "left"},
        {"key": "num", "label": "№", "kind": "mono", "align": "left"},
        {"key": "supplier", "label": "Поставщик", "kind": "text", "align": "left"},
        {"key": "deliv", "label": "Поставка", "kind": "text", "align": "left"},
        {"key": "pct", "label": "% позиций", "kind": "percent", "align": "right"},
        {"key": "srok", "label": "Срок ДД", "kind": "date-late", "align": "left"},
    ]
    rows_d = []
    for p, d, lt in late_dels:
        par = ctx.parent_by_proc.get(p.id, {})
        positions = ctx.positions_by_proc.get(p.id, [])
        dels = ctx.deliveries_by_proc.get(p.id, [])
        pct = overdue_pct(positions, dels, p.srok_dd, today)
        rows_d.append([
            _claim(par.get("code"), par.get("title")),
            p.proc or "—",
            p.supplier or "—",
            f"№{d.n}" + (" (с задержкой)" if lt else ""),
            _pct(pct),
            _date_late(p.srok_dd),
        ])
    if not rows_d:
        rows_d = [_empty_note_row(len(cols_d))]
    sec_d = {"title": "Поставки", "columns": cols_d, "rows": rows_d, "footer": None}

    cols_p = [
        {"key": "upd", "label": "УПД", "kind": "mono", "align": "left"},
        {"key": "claim", "label": "Заявка", "kind": "claim", "align": "left"},
        {"key": "supplier", "label": "Поставщик", "kind": "text", "align": "left"},
        {"key": "sum", "label": "Сумма", "kind": "money", "align": "right"},
    ]
    rows_p = []
    for u in late_upds:
        claim = _upd_claim(u, ctx)
        rows_p.append([u.upd, claim, u.supplier or "—", _money(u.amount or 0)])
    if not rows_p:
        rows_p = [_empty_note_row(len(cols_p))]
    sec_p = {"title": "Оплаты", "columns": cols_p, "rows": rows_p, "footer": None}

    return _snapshot("late", "Просрочки: поставки и оплаты", ctx, kpis, [sec_d, sec_p])
```

- [ ] **Step 4: Run tests to verify them pass**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "late_" -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_reports.py
git commit -m "feat(reports): report_late — просрочки поставок и оплат (Phase 9.1 T5)"
```

---

## Task 6: `report_people` — сводка по составителям/отделам

**Files:**
- Modify: `backend/app/calculations.py` (replace `report_people` stub)
- Test: `backend/tests/test_reports.py` (append)

**Interfaces:**
- Consumes: `_load_report_ctx`, `proc_sum`, cell helpers; `User` model (dept fallback).
- Produces: real `report_people` → 1 section (Составитель · Отдел · Заявок (Т-) · Доч. заявок · Сумма договоров), grouped by `sostavitel`. Universe = parents with `status != 'cancelled'`. `dept` = `parent.dept`, fallback `created_by → user.department`, else «—». Σ = `proc_sum` over non-`Отменена` procedures. Sorted by Σ desc.

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 9.1 Task 6: report_people -------------------------------------------------

def test_people_group_by_sostavitel(client_admin, db_seeded):
    # create requests as admin (full_name "Администратор"); set sostavitel explicitly via DB
    _create_request(client_admin, "PE-1", "t1", POS)
    _create_request(client_admin, "PE-2", "t2", POS)
    from app.models import ParentRequest
    db_seeded.query(ParentRequest).filter_by(code="PE-1").update({"sostavitel": "Орлова А."})
    db_seeded.query(ParentRequest).filter_by(code="PE-2").update({"sostavitel": "Седов В."})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    rows = {r[0]: r for r in snap["sections"][0]["rows"]}
    assert "Орлова А." in rows and "Седов В." in rows
    assert rows["Орлова А."][2] == "1"   # 1 заявка


def test_people_counts_procedures_and_sum(client_admin, db_seeded):
    # one parent with one procedure in zakupka; set contract_sum explicitly
    pid = _to_zakupka(client_admin, "PE-P1", "p1", POS)
    _set_proc(db_seeded, pid, contract_sum=200000)                 # 2 000 ₽
    from app.models import ParentRequest, Procedure, Tender
    par_id = db_seeded.query(Tender).join(Procedure, Procedure.tender_id == Tender.id).filter(Procedure.id == pid).first().parent_id
    db_seeded.query(ParentRequest).filter_by(id=par_id).update({"sostavitel": "Орлова А."})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    row = next(r for r in snap["sections"][0]["rows"] if r[0] == "Орлова А.")
    assert row[3] == "1"                  # 1 procedure
    assert row[4]["text"] == "2 000 ₽"


def test_people_excludes_cancelled_parent(client_admin, db_seeded):
    _create_request(client_admin, "PE-CA", "ca", POS)
    from app.models import ParentRequest
    db_seeded.query(ParentRequest).filter_by(code="PE-CA").update({"sostavitel": "X", "status": "cancelled"})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    assert all(r[0] != "X" for r in snap["sections"][0]["rows"])


def test_people_dept_fallback(client_admin, db_seeded):
    # parent.dept null → fallback to creator's department
    _create_request(client_admin, "PE-D1", "d1", POS)
    from app.models import ParentRequest
    db_seeded.query(ParentRequest).filter_by(code="PE-D1").update({"sostavitel": "Z", "dept": None})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    row = next(r for r in snap["sections"][0]["rows"] if r[0] == "Z")
    # admin has no department → "—"
    assert row[1] == "—"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "people_" -v`
Expected: FAIL — `report_people` returns empty sections.

- [ ] **Step 3: Replace the `report_people` stub in `backend/app/calculations.py`**

```python
def report_people(db, today: date, flt: dict) -> dict:
    """Сводка по составителям/отделам (spec R7/R8)."""
    from app.models import ParentRequest, Procedure, Tender, User

    ctx = _load_report_ctx(db, today, flt)
    has_period = ctx.has_period
    mtr = flt.get("mtr")
    author = flt.get("author")

    def in_period(zagruzka_iso):
        if not has_period:
            return True
        zg = _parse_date(zagruzka_iso)
        return zg is not None and ctx.from_d <= zg <= ctx.to_d

    # procedures grouped by their parent's sostavitel
    procs_by_parent: dict = defaultdict(list)
    for p in ctx.procs:
        # parent may be outside ctx filter set if filtered by supplier/mtr — but ctx.procs are filtered;
        # find parent id via tender
        pass
    # Build parent→procs map from a fresh query over ALL non-cancelled parents passing filters,
    # so awaiting-only parents (no procedures) still appear.
    q = db.query(ParentRequest).filter(ParentRequest.status != "cancelled")
    user_dept = {u_id: u_dept for u_id, u_dept in db.query(User.id, User.department).all()}
    groups: dict = {}  # sostavitel -> {dept, parents:set, proc_count, sum}
    for par in q.all():
        if mtr and par.mtr != mtr:
            continue
        if author and par.sostavitel != author:
            continue
        if not in_period(par.zagruzka):
            continue
        dept = par.dept or user_dept.get(par.created_by) or "—"
        g = groups.setdefault(par.sostavitel or "—", {"dept": dept, "parents": set(), "proc_count": 0, "sum": 0})
        g["parents"].add(par.id)
    # attach procedures of these parents
    parent_ids = [pid for g in groups.values() for pid in g["parents"]] or [0]
    proc_rows = (
        db.query(Procedure, Tender.parent_id)
        .join(Tender, Procedure.tender_id == Tender.id)
        .filter(Tender.parent_id.in_(parent_ids))
        .all()
    )
    pos_by_proc = ctx.positions_by_proc  # positions for ctx-filtered procs; recompute for all
    # positions for procs possibly outside ctx filter: load by these proc ids
    proc_ids_all = [p.id for p, _pid in proc_rows] or [0]
    from app.models import ProcedurePosition
    pos_rows = db.query(ProcedurePosition).filter(ProcedurePosition.procedure_id.in_(proc_ids_all)).all()
    pos_map = defaultdict(list)
    for pp in pos_rows:
        pos_map[pp.procedure_id].append(pp)
    parent_of_proc = {p.id: pid for p, pid in proc_rows}
    for p, pid in proc_rows:
        # find the group by parent's sostavitel
        par = db.query(ParentRequest).filter_by(id=pid).first()
        if par is None or par.status == "cancelled":
            continue
        key = par.sostavitel or "—"
        if key not in groups:
            continue
        if p.status_zakup == "Отменена" or p.status_postavki == "Отменена":
            continue
        groups[key]["proc_count"] += 1
        groups[key]["sum"] += proc_sum(p, pos_map.get(p.id, []))

    cols = [
        {"key": "sost", "label": "Составитель", "kind": "text", "align": "left"},
        {"key": "dept", "label": "Отдел", "kind": "text", "align": "left"},
        {"key": "n", "label": "Заявок (Т-)", "kind": "num", "align": "right"},
        {"key": "sub", "label": "Доч. заявок", "kind": "num", "align": "right"},
        {"key": "sum", "label": "Сумма договоров", "kind": "money", "align": "right"},
    ]
    items = sorted(groups.items(), key=lambda kv: kv[1]["sum"], reverse=True)
    rows = [[sost, g["dept"], str(len(g["parents"])), str(g["proc_count"]), _money(g["sum"])]
            for sost, g in items]
    section = {"title": None, "columns": cols, "rows": rows, "footer": None}
    return _snapshot("people", "Сводка по составителям/отделам", ctx, [], [section])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "people_" -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_reports.py
git commit -m "feat(reports): report_people — сводка по составителям/отделам (Phase 9.1 T6)"
```

---

## Task 7: export (Excel/PDF/CSV) + `GET /reports/{type}/export`

**Files:**
- Create: `backend/app/export.py`
- Create: `backend/app/fonts/DejaVuSans.ttf`, `backend/app/fonts/DejaVuSans-Bold.ttf` (bundle; or rely on Windows fallback)
- Modify: `backend/app/routers/reports.py` (add the export route)
- Test: `backend/tests/test_reports.py` (append)

**Interfaces:**
- Consumes: the generic snapshot (dict) from builders; `reportlab`, `openpyxl`.
- Produces: `render_csv(snapshot)→str`, `render_excel(snapshot)→BytesIO`, `render_pdf(snapshot)→BytesIO`, `_register_fonts()→(normal,bold)`; route `GET /reports/{type}/export?format=excel|pdf|csv` returning a file with correct `Content-Type` + `Content-Disposition`. Money/date cells render as their `text`.

**Authority:** spec R9/R10/R12. PDF needs a Cyrillic TTF — `_register_fonts` prefers bundled `backend/app/fonts/DejaVuSans*.ttf`, else falls back to `C:\\Windows\\Fonts\\arial*.ttf`, else raises.

- [ ] **Step 1: Add the failing tests (append)**

```python
# --- 9.1 Task 7: export --------------------------------------------------------

def test_export_csv_content_type_and_body(client_admin, db_seeded):
    _to_zakupka(client_admin, "X-1", "x1", POS)
    r = client_admin.get("/reports/time/export?format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")            # UTF-8 BOM
    assert "Время на этапе" in r.text
    assert "content-disposition" in {k.lower() for k in r.headers}
    assert ".csv" in r.headers["content-disposition"]


def test_export_excel(client_admin):
    r = client_admin.get("/reports/sums/export?format=excel")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"                            # xlsx zip signature
    assert ".xlsx" in r.headers["content-disposition"]


def test_export_pdf(client_admin):
    r = client_admin.get("/reports/late/export?format=pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert ".pdf" in r.headers["content-disposition"]


def test_export_unknown_format_422(client_admin):
    assert client_admin.get("/reports/time/export?format=docx").status_code == 422


def test_export_unknown_type_404(client_admin):
    assert client_admin.get("/reports/bogus/export?format=csv").status_code == 404


def test_export_forbidden_employee(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "k3@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time/export?format=csv").status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "export_" -v`
Expected: FAIL — `/reports/time/export` → 404 (route not added yet).

- [ ] **Step 3: (Optional but recommended) bundle DejaVuSans TTFs**

Try to download DejaVuSans (OFL) into `backend/app/fonts/`. If the machine is offline or download fails, the Windows `arial.ttf` fallback (next step) covers dev/tests.

```bash
cd backend/app/fonts
curl -fsSL -o DejaVuSans.ttf https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf || true
curl -fsSL -o DejaVuSans-Bold.ttf https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf || true
ls -la
```

If the files are present (>100 KB each), `git add backend/app/fonts/DejaVuSans*.ttf` (they are committed binaries). If absent, proceed — `_register_fonts` falls back to the system font.

- [ ] **Step 4: Write `backend/app/export.py` (complete)**

```python
"""Report export renderers (Phase 9.1) — CSV / Excel / PDF from a generic snapshot.

The snapshot is the dict returned by calculations.report_* : {type,title,period,kpis,sections}.
Money/date cells are pre-formatted strings; this module only renders `text`.
PDF needs a Cyrillic-capable TTF (reportlab built-ins don't render Cyrillic) — see _register_fonts.
Spec: docs/superpowers/specs/2026-06-28-phase9-reports-design.md (R9/R10).
"""
from __future__ import annotations

import io
import os


def _cell_text(cell) -> str:
    """Plain-text rendering of a cell (str or styled object)."""
    if isinstance(cell, dict):
        if cell.get("kind") == "claim":
            code = cell.get("code") or "—"
            title = cell.get("title") or ""
            return f"{code} {title}".strip()
        return cell.get("text") or ""
    return str(cell)


# ---------------------------------------------------------------- CSV

def render_csv(snap: dict) -> str:
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM — Excel opens Cyrillic correctly
    import csv
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow([snap["title"]])
    if snap.get("period"):
        p = snap["period"]
        w.writerow([p["label"], p.get("from", ""), p.get("to", "")])
    for kpi in snap["kpis"]:
        w.writerow([kpi["label"], kpi["value"]])
    for sec in snap["sections"]:
        if sec.get("title"):
            w.writerow([])
            w.writerow([sec["title"]])
        w.writerow([c["label"] for c in sec["columns"]])
        for row in sec["rows"]:
            w.writerow([_cell_text(c) for c in row])
        if sec.get("footer"):
            w.writerow([_cell_text(c) for c in sec["footer"]])
    return buf.getvalue()


# ---------------------------------------------------------------- Excel

def render_excel(snap: dict) -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Отчёт"
    r = 1
    ws.cell(r, 1, snap["title"]).font = Font(bold=True, size=14)
    r += 1
    if snap.get("period"):
        p = snap["period"]
        ws.cell(r, 1, p["label"]); ws.cell(r, 2, p.get("from", "")); ws.cell(r, 3, p.get("to", ""))
        r += 1
    for kpi in snap["kpis"]:
        ws.cell(r, 1, kpi["label"]); ws.cell(r, 2, kpi["value"])
        r += 1
    for sec in snap["sections"]:
        if sec.get("title"):
            ws.cell(r, 1, sec["title"]).font = Font(bold=True)
            r += 1
        for j, col in enumerate(sec["columns"], 1):
            ws.cell(r, j, col["label"]).font = Font(bold=True)
        r += 1
        for row in sec["rows"]:
            for j, c in enumerate(row, 1):
                ws.cell(r, j, _cell_text(c))
            r += 1
        if sec.get("footer"):
            for j, c in enumerate(sec["footer"], 1):
                ws.cell(r, j, _cell_text(c)).font = Font(bold=True)
            r += 1
        r += 1
    for col in ws.columns:
        maxlen = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(maxlen + 2, 60)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------- PDF

_FONT_CACHE = None


def _register_fonts():
    """Return (normal_name, bold_name) of a Cyrillic-capable TTF registered with reportlab.

    Priority: bundled backend/app/fonts/DejaVuSans*.ttf → Windows arial*.ttf → error.
    """
    global _FONT_CACHE
    if _FONT_CACHE:
        return _FONT_CACHE
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    here = os.path.dirname(__file__)
    candidates = [
        (os.path.join(here, "fonts", "DejaVuSans.ttf"),
         os.path.join(here, "fonts", "DejaVuSans-Bold.ttf"), "DJ", "DJB"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf", "AR", "ARB"),
        (r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\consolab.ttf", "CON", "CONB"),
    ]
    for normal, bold, nname, bname in candidates:
        if os.path.exists(normal):
            try:
                pdfmetrics.registerFont(TTFont(nname, normal))
                bold_name = nname
                if os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont(bname, bold))
                    bold_name = bname
                _FONT_CACHE = (nname, bold_name)
                return _FONT_CACHE
            except Exception:
                continue
    raise RuntimeError(
        "No Cyrillic-capable TTF found for PDF export. "
        "Bundle DejaVuSans.ttf in backend/app/fonts/ or run on Windows."
    )


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_pdf(snap: dict) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font_normal, font_bold = _register_fonts()
    s_title = ParagraphStyle("t", fontName=font_bold, fontSize=14, leading=18)
    s_meta = ParagraphStyle("m", fontName=font_normal, fontSize=9, leading=12, textColor=colors.HexColor("#666666"))
    s_kpi = ParagraphStyle("k", fontName=font_normal, fontSize=9, leading=13)
    s_h = ParagraphStyle("h", fontName=font_bold, fontSize=10, leading=14, spaceBefore=6)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=12 * mm, leftMargin=12 * mm, rightMargin=12 * mm, bottomMargin=12 * mm)
    elems = [Paragraph(_escape(snap["title"]), s_title)]
    if snap.get("period"):
        p = snap["period"]
        elems.append(Paragraph(
            _escape(f"{p['label']}: {p.get('from', '')} — {p.get('to', '')}"), s_meta))
    elems.append(Paragraph(
        _escape(" · ".join(f"{k['label']}: {k['value']}" for k in snap["kpis"])), s_kpi))
    elems.append(Spacer(1, 6))

    page_w = A4[0] - 24 * mm
    for sec in snap["sections"]:
        if sec.get("title"):
            elems.append(Paragraph(_escape(sec["title"]), s_h))
        data = [[_escape(c["label"]) for c in sec["columns"]]]
        aligns = [c.get("align") for c in sec["columns"]]
        for row in sec["rows"]:
            data.append([_escape(_cell_text(c)) for c in row])
        if sec.get("footer"):
            data.append([_escape(_cell_text(c)) for c in sec["footer"]])
        ncol = len(sec["columns"])
        widths = [page_w / ncol] * ncol
        t = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("FONT", (0, 0), (-1, -1), font_normal, 8),
            ("FONT", (0, 0), (-1, 0), font_bold, 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef0f3")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for j, a in enumerate(aligns):
            if a == "right":
                style.append(("ALIGN", (j, 0), (j, -1), "RIGHT"))
        if sec.get("footer"):
            style.append(("FONT", (0, -1), (-1, -1), font_bold, 8))
            style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black))
        t.setStyle(TableStyle(style))
        elems.append(t)
        elems.append(Spacer(1, 8))

    doc.build(elems)
    buf.seek(0)
    return buf
```

- [ ] **Step 5: Add the export route to `backend/app/routers/reports.py`**

Add imports at the top:

```python
from fastapi import Response
from app import export as export_mod
```

Append the route (after `get_report`):

```python
@router.get("/{type}/export")
def export_report(
    type: str,
    format: str = Query(...),
    period: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    mtr: Optional[str] = Query(default=None),
    supplier: Optional[str] = Query(default=None),
    author: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_action("reports", "view")),
) -> Response:
    if type not in REPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown report type")
    if format not in ("excel", "pdf", "csv"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown format")
    flt = _build_flt(period, date_from, date_to, mtr, supplier, author)
    _validate_period(flt)
    snap = _BUILDERS[type](db, calc.today_moscow(), flt)
    today_iso = calc.today_moscow().isoformat()
    filename = f"otchety_{type}_{today_iso}"
    if format == "csv":
        body = export_mod.render_csv(snap).encode("utf-8")
        return Response(body, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})
    if format == "excel":
        buf = export_mod.render_excel(snap)
        return Response(buf.getvalue(),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'})
    # pdf
    buf = export_mod.render_pdf(snap)
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_reports.py -k "export_" -v`
Expected: 6 passed. (PDF test passes via bundled DejaVu OR Windows arial fallback.)

- [ ] **Step 7: Run the FULL backend suite (no regressions)**

Run: `cd backend && "$PY" -m pytest -q`
Expected: all green (386 prior + new test_reports tests, 0 failures).

- [ ] **Step 8: Commit**

```bash
git add backend/app/export.py backend/app/routers/reports.py backend/tests/test_reports.py
# also add bundled fonts if downloaded in Step 3:
git add backend/app/fonts/DejaVuSans.ttf backend/app/fonts/DejaVuSans-Bold.ttf 2>/dev/null || true
git commit -m "feat(reports): Excel/PDF/CSV export + export route (Phase 9.1 T7)"
```

---

## ⏸ STOP — Phase 9.1 verification (before Frontend 9.2)

- [ ] `cd backend && "$PY" -m pytest -q` → all green, 0 failures.
- [ ] `cd backend && "$PY" -m pip install openpyxl reportlab` succeeded; both importable.
- [ ] Spot-check via TestClient (or curl against dev server on :8000, logged in as admin):
  - `GET /reports` → `{mtr[],supplier[],author[]}` non-empty after seeding data.
  - `GET /reports/time|sums|late|people` → each returns a snapshot with correct KPIs/columns on a small dev-DB slice (hand-verify vs `32 §8`).
  - `GET /reports/sums/export?format=excel|pdf|csv` → each downloads a non-empty file with the right `Content-Type`; open the CSV in Excel — Cyrillic renders (BOM), `;`-separated; open the PDF — Cyrillic renders (font resolved).
  - `GET /reports/time` under a department employee → 403; under Куратор/Руководитель → 200.
- [ ] **Wait for user confirmation before Frontend 9.2.**

🔎 After Frontend 9.2 (next plan): ui-checker on the «Отчёты» page (types switching, sticky params, tables/KPIs, export buttons, tab visibility by role).
