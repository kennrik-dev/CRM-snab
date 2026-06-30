# Phase 10 — Backend Implementation Plan (search + comments + history + backup)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the global-search spec gap (+№ заявки, +№ УПД), add `GET/POST/DELETE /comments`, add `GET /history` (audit read), fix the `parent_request`→`parent` audit inconsistency, and add `scripts/backup.py` + an Alembic pre-migration backup hook.

**Architecture:** Thin FastAPI routers mirroring `reports.py`/`payments.py`. Comments reuse the existing (dead) `Comment` table; history reads the existing `audit_log` (action-only, no schema change). All reads/auth use `require_password_changed` (global, like `/search`); comment delete adds an author-or-Админ check via `can()`. Backup uses sqlite3 online-backup. No DB migration.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest + httpx `TestClient`, in-memory SQLite (`create_all`, `register_sqlite_setup` registers `py_casefold`).

## Global Constraints (copied verbatim from `docs/`)

- **Язык** — русский (`ru-RU`); UI/audit-строки на русском.
- **Деньги** — `INTEGER` копейки; **в Фазе 10 новых денежных полей нет.**
- **Даты** — ISO `YYYY-MM-DD`; метки `YYYY-MM-DD HH:MM:SS` (server_default `datetime('now')`).
- **Часовой пояс** — Europe/Moscow.
- **Кириллица в поиске** — только `func.py_casefold(...)` (встроенный `lower()` ASCII-only). `tests/conftest.py` уже регистрирует `py_casefold` на тестовом соединении — НОВЫЕ тестовые файлы должны использовать тот же паттерн (см. `test_search.py`).
- **Пагинация** — `?page=&page_size=` (по умолчанию 50), ответ `{items, total}`.
- **Коды ошибок** — 401 / 403 / 404 / 422.
- **Аудит** — каждый мутирующий запрос пишет `audit_log` (`write_audit`).
- **Python на этой машине** — `python` из Git Bash это MS Store stub; используйте абсолютный интерпретатор: `PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/routers/search.py` | Extend: +`tenders` (Tender.num) + `payments` (UpdPayment.upd) groups; +`block` on procedures group |
| `backend/app/routers/comments.py` | NEW: `GET/POST/DELETE /comments`; author snapshot server-side; delete = author\|Админ; audit on POST/DELETE |
| `backend/app/routers/history.py` | NEW: `GET /history?entity_kind=&entity_id=`; newest-first; actor via User join |
| `backend/app/schemas/comments.py` | NEW: `CommentOut`, `CommentCreate`, `CommentList` |
| `backend/app/schemas/history.py` | NEW: `AuditEntryOut`, `HistoryList` |
| `backend/app/backup.py` | NEW: `run_backup(db_path, backup_dir, keep=14)` (sqlite3 online backup + rotation) |
| `scripts/backup.py` | NEW: thin CLI wrapper over `app.backup.run_backup` |
| `backend/migrations/env.py` | Call `run_backup()` before online `run_migrations()` |
| `backend/app/main.py` | Include `comments`, `history` routers |
| `backend/app/routers/requests.py` | Fix `'parent_request'`→`'parent'` |
| `backend/tests/test_search.py` | Extend: +tenders/payments; update 5-group assertions |
| `backend/tests/test_comments.py` | NEW |
| `backend/tests/test_history.py` | NEW |
| `backend/tests/test_backup.py` | NEW |
| `backend/tests/test_requests.py` | +regression: audit uses `'parent'` |

---

## Task B1: Extend GET /search (+tenders, +payments, +block on procedures)

**Files:**
- Modify: `backend/app/routers/search.py` (whole `global_search` body + imports)
- Test: `backend/tests/test_search.py`

**Interfaces:**
- Consumes: `func.py_casefold` (from `app.db` event registration); models `ParentRequest, Procedure, Tender, UpdPayment`.
- Produces: `GET /search` → `{parents, procedures, suppliers, tenders, payments}` where `procedures[*]` now includes `block`; `tenders[*]={id,num,parent_id,parent_code}`; `payments[*]={id,upd,supplier}`. Empty `q` → all five groups `[]`.

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/test_search.py`.

Add a helper near the other `_make_*` helpers:

```python
def _make_upd_payment(db, upd: str, supplier: str | None = None):
    from app.models import UpdPayment
    p = UpdPayment(upd=upd, origin="manual", supplier=supplier, amount=0, pay_status="await")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p
```

Update the four empty-response assertions to expect 5 groups. Replace every occurrence of:

```python
assert body == {"parents": [], "procedures": [], "suppliers": []}
```

with:

```python
assert body == {"parents": [], "procedures": [], "suppliers": [], "tenders": [], "payments": []}
```

(These appear in `test_search_empty_q_returns_empty_groups_without_db_calls`, `test_search_whitespace_q_returns_empty_groups`, `test_search_no_data_returns_empty_groups`, `test_search_no_match_returns_empty_groups`. In the first one the variable is `body`; in `test_search_no_match_returns_empty_groups` it is `r.json()` — replace accordingly as `assert r.json() == {"parents": [], "procedures": [], "suppliers": [], "tenders": [], "payments": []}`.)

Append new tests:

```python
# ---------------------------------------------------------------------------
# /search — tenders (№ заявки = Tender.num)
# ---------------------------------------------------------------------------

def test_search_tender_num_match(client_admin, db_seeded):
    parent = _make_parent(db_seeded, code="Т-10", title="T")
    _make_tender(db_seeded, num="З-1488", parent_id=parent.id)

    r = client_admin.get("/search?q=1488")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["tenders"]) == 1
    t = body["tenders"][0]
    assert set(t.keys()) >= {"id", "num", "parent_id", "parent_code"}
    assert t["num"] == "З-1488"
    assert t["parent_id"] == parent.id
    assert t["parent_code"] == "Т-10"


def test_search_tender_num_match_case_insensitive_cyrillic(client_admin, db_seeded):
    parent = _make_parent(db_seeded, code="Т-11", title="T")
    _make_tender(db_seeded, num="Заявка-А", parent_id=parent.id)

    r = client_admin.get("/search?q=заявка")
    assert r.status_code == 200, r.text
    assert len(r.json()["tenders"]) == 1


# ---------------------------------------------------------------------------
# /search — payments (№ УПД = UpdPayment.upd)
# ---------------------------------------------------------------------------

def test_search_payment_upd_match(client_admin, db_seeded):
    _make_upd_payment(db_seeded, upd="УПД-777", supplier="ООО Ромашка")

    r = client_admin.get("/search?q=777")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["payments"]) == 1
    pm = body["payments"][0]
    assert set(pm.keys()) >= {"id", "upd", "supplier"}
    assert pm["upd"] == "УПД-777"
    assert pm["supplier"] == "ООО Ромашка"


def test_search_procedures_now_include_block(client_admin, db_seeded):
    parent = _make_parent(db_seeded, code="B-1", title="B")
    tender = _make_tender(db_seeded, num="B-1", parent_id=parent.id)
    _make_procedure(db_seeded, tender_id=tender.id, proc="PR-1", supplier="S")

    r = client_admin.get("/search?q=PR-1")
    assert r.status_code == 200, r.text
    p = r.json()["procedures"][0]
    assert "block" in p
    assert p["block"] == "zakupka"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_search.py -q` (with `PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`)
Expected: FAIL — `KeyError: 'tenders'` / `'payments'` / `'block'`, and the updated empty-response asserts fail with extra-key mismatch.

- [ ] **Step 3: Implement** — replace `backend/app/routers/search.py` imports (line 27) and the whole `global_search` body.

Imports — change line 27 from:

```python
from app.models import ParentRequest, Procedure, User
```

to:

```python
from app.models import ParentRequest, Procedure, Tender, UpdPayment, User
```

Replace the body of `global_search` (from `empty = {...}` through the final `return {...}`):

```python
    empty = {"parents": [], "procedures": [], "suppliers": [], "tenders": [], "payments": []}

    q_stripped = q.strip()
    if not q_stripped:
        return empty

    q_cf = q_stripped.casefold()

    # parents — code OR title
    code_match = func.instr(func.py_casefold(ParentRequest.code), q_cf) > 0
    title_match = func.instr(func.py_casefold(ParentRequest.title), q_cf) > 0
    parents = (
        db.query(ParentRequest.id, ParentRequest.code, ParentRequest.title)
        .filter(code_match | title_match)
        .order_by(ParentRequest.created_at.desc())
        .limit(limit)
        .all()
    )

    # procedures — proc IS NOT NULL AND matches; include block for FE routing
    procedures = (
        db.query(
            Procedure.id,
            Procedure.proc,
            Procedure.supplier,
            Procedure.tender_id,
            Procedure.block,
        )
        .filter(Procedure.proc.isnot(None))
        .filter(func.instr(func.py_casefold(Procedure.proc), q_cf) > 0)
        .order_by(Procedure.created_at.desc())
        .limit(limit)
        .all()
    )

    # suppliers — distinct, with proc_count (id = min(procedure.id) representative)
    supplier_rows = (
        db.query(
            func.min(Procedure.id).label("id"),
            Procedure.supplier.label("name"),
            func.count(Procedure.id).label("proc_count"),
        )
        .filter(Procedure.supplier.isnot(None))
        .filter(func.instr(func.py_casefold(Procedure.supplier), q_cf) > 0)
        .group_by(Procedure.supplier)
        .order_by(func.count(Procedure.id).desc(), Procedure.supplier.asc())
        .limit(limit)
        .all()
    )

    # tenders — № заявки (Tender.num); join parent for code → FE nav target
    tenders = (
        db.query(
            Tender.id,
            Tender.num,
            Tender.parent_id,
            ParentRequest.code.label("parent_code"),
        )
        .join(ParentRequest, Tender.parent_id == ParentRequest.id)
        .filter(Tender.num.isnot(None))
        .filter(func.instr(func.py_casefold(Tender.num), q_cf) > 0)
        .order_by(Tender.id.desc())
        .limit(limit)
        .all()
    )

    # payments — № УПД (UpdPayment.upd, NOT NULL)
    payments = (
        db.query(UpdPayment.id, UpdPayment.upd, UpdPayment.supplier)
        .filter(func.instr(func.py_casefold(UpdPayment.upd), q_cf) > 0)
        .order_by(UpdPayment.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "parents": [
            {"id": p.id, "code": p.code, "title": p.title} for p in parents
        ],
        "procedures": [
            {
                "id": pr.id,
                "proc": pr.proc,
                "supplier": pr.supplier,
                "tender_id": pr.tender_id,
                "block": pr.block,
            }
            for pr in procedures
        ],
        "suppliers": [
            {"id": s.id, "name": s.name, "proc_count": s.proc_count}
            for s in supplier_rows
        ],
        "tenders": [
            {
                "id": t.id,
                "num": t.num,
                "parent_id": t.parent_id,
                "parent_code": t.parent_code,
            }
            for t in tenders
        ],
        "payments": [
            {"id": pm.id, "upd": pm.upd, "supplier": pm.supplier}
            for pm in payments
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_search.py -q`
Expected: PASS (all, including the new tenders/payments/block tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/search.py backend/tests/test_search.py
git commit -m "feat(search): +tenders/№ заявки and payments/№ УПД groups, +block on procedures (Phase 10 B1)"
```

---

## Task B2: Comments router (GET / POST / DELETE) + schemas

**Files:**
- Create: `backend/app/routers/comments.py`
- Create: `backend/app/schemas/comments.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_comments.py`

**Interfaces:**
- Consumes: `Comment` model (`target_kind ∈ parent/tender/procedure`, `target_id`, `author_id`, `author`, `role`, `text`, `created_at`); `write_audit(db, entity_kind, entity_id, user, action)`; `paginate(query, page, page_size=50)`; `require_password_changed`; `can(user, 'admin', 'view')`; models `ParentRequest, Tender, Procedure`.
- Produces:
  - `GET /comments?target_kind=&target_id=&page=&page_size=` → `CommentList{items:CommentOut[], total}` (asc).
  - `POST /comments` body `CommentCreate{target_kind, target_id, text}` → `CommentOut` (201).
  - `DELETE /comments/{id}` → 204.
  - `CommentOut = {id, target_kind, target_id, author_id, author, role, text, created_at}`.

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_comments.py`.

```python
"""Tests for /comments router (Phase 10 B2). Spec: docs/31 §7, docs/01 §2.7."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password
from app.models import Comment, AuditLog, ParentRequest, User

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"


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


def _login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def client_admin(client_seeded):
    """Admin with must_change_password=0 (change then re-login)."""
    _login(client_seeded, ADMIN_EMAIL, ADMIN_INITIAL_PASSWORD)
    r = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD},
    )
    assert r.status_code == 200, r.text
    client_seeded.post("/auth/logout")
    _login(client_seeded, ADMIN_EMAIL, ADMIN_NEW_PASSWORD)
    return client_seeded


def _make_dept_user(db, email, department, curator=False, password="pass12345"):
    u = User(
        email=email,
        password_hash=hash_password(password),
        full_name=email.split("@")[0].title(),
        account_type="department",
        department=department,
        is_curator=1 if curator else 0,
        global_role=None,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_parent(db, code="Т-1"):
    p = ParentRequest(code=code, title="T", sostavitel="S")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# POST /comments
# ---------------------------------------------------------------------------

def test_create_comment_fills_author_and_role_snapshot(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments",
        json={"target_kind": "parent", "target_id": parent.id, "text": "Привет!"},
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["text"] == "Привет!"
    assert c["target_kind"] == "parent"
    assert c["target_id"] == parent.id
    # author/role filled server-side from the session user (admin)
    assert c["author"] and c["author"] == "Админ" or c["role"] in ("Админ",)
    assert c["author_id"] is not None
    assert "created_at" in c


def test_create_comment_writes_audit(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "x"}
    )
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=parent.id)
        .all()
    )
    assert any("комментар" in (row.action or "").lower() for row in rows)


def test_create_comment_rejects_bad_target_kind(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments",
        json={"target_kind": "delivery", "target_id": parent.id, "text": "x"},
    )
    assert r.status_code == 422, r.text


def test_create_comment_rejects_empty_text(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments",
        json={"target_kind": "parent", "target_id": parent.id, "text": "   "},
    )
    assert r.status_code == 422, r.text


def test_create_comment_404_when_target_missing(client_admin, db_seeded):
    r = client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": 999999, "text": "x"}
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# GET /comments
# ---------------------------------------------------------------------------

def test_list_comments_filtered_and_ascending(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    for txt in ("первый", "второй", "третий"):
        client_admin.post(
            "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": txt}
        )
    other = _make_parent(db_seeded, code="Т-2")
    client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": other.id, "text": "чужей"}
    )
    r = client_admin.get(f"/comments?target_kind=parent&target_id={parent.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert [c["text"] for c in body["items"]] == ["первый", "второй", "третий"]


# ---------------------------------------------------------------------------
# DELETE /comments/{id}
# ---------------------------------------------------------------------------

def test_delete_own_comment_as_author(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "x"}
    )
    cid = r.json()["id"]
    d = client_admin.delete(f"/comments/{cid}")
    assert d.status_code == 204, d.text
    assert db_seeded.query(Comment).filter_by(id=cid).first() is None


def test_delete_others_comment_as_non_author_forbidden(client_seeded, db_seeded):
    author = _make_dept_user(db_seeded, "a@x.local", "Закупки")
    other = _make_dept_user(db_seeded, "b@x.local", "Закупки")
    parent = _make_parent(db_seeded)
    _login(client_seeded, author.email, "pass12345")
    r = client_seeded.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "мной"}
    )
    cid = r.json()["id"]
    client_seeded.post("/auth/logout")
    _login(client_seeded, other.email, "pass12345")
    d = client_seeded.delete(f"/comments/{cid}")
    assert d.status_code == 403, d.text


def test_delete_others_comment_as_admin_ok(client_seeded, db_seeded):
    author = _make_dept_user(db_seeded, "a@x.local", "Закупки")
    parent = _make_parent(db_seeded)
    _login(client_seeded, author.email, "pass12345")
    r = client_seeded.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "мной"}
    )
    cid = r.json()["id"]
    client_seeded.post("/auth/logout")
    _login(client_seeded, ADMIN_EMAIL, ADMIN_NEW_PASSWORD)
    d = client_seeded.delete(f"/comments/{cid}")
    assert d.status_code == 204, d.text


def test_delete_missing_comment_404(client_admin):
    assert client_admin.delete("/comments/999999").status_code == 404


# ---------------------------------------------------------------------------
# auth gating
# ---------------------------------------------------------------------------

def test_comments_unauthenticated_401(client_seeded):
    assert client_seeded.get("/comments?target_kind=parent&target_id=1").status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_comments.py -q`
Expected: FAIL — 404 for `/comments` (router not registered).

- [ ] **Step 3: Implement** — create `backend/app/schemas/comments.py`:

```python
"""Pydantic schemas for /comments (Phase 10 B2). Mirror backend columns."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    target_kind: Literal["parent", "tender", "procedure"]
    target_id: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_kind: str
    target_id: int
    author_id: Optional[int] = None
    author: Optional[str] = None
    role: Optional[str] = None
    text: str
    created_at: str


class CommentList(BaseModel):
    items: list[CommentOut]
    total: int
```

Create `backend/app/routers/comments.py`:

```python
"""/comments router (Phase 10 B2) — лента + добавление + удаление.

Auth = require_password_changed (все аутентифицированные; «единое окно»).
Автор = текущий пользователь (снимок ФИО/роли server-side). Удаление: автор
своего ИЛИ Админ. POST/DELETE пишут audit_log. Spec: docs/31 §7, docs/01 §2.7.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.audit import paginate, write_audit
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import Comment, ParentRequest, Procedure, Tender, User
from app.permissions import can
from app.schemas.comments import CommentCreate, CommentList, CommentOut

router = APIRouter(prefix="/comments", tags=["comments"])

_TARGET_MODELS = {"parent": ParentRequest, "tender": Tender, "procedure": Procedure}


def _role_snapshot(user: User) -> str:
    """Human role label mirror of FE roleLabel (dashView). Snapshot survives deactivation."""
    if user.global_role:  # Админ / Руководитель
        return user.global_role
    if user.account_type == "global":
        return "Куратор"
    base = user.department or "—"
    return f"{base} · куратор" if user.is_curator else base


def _target_exists(db: Session, target_kind: str, target_id: int) -> bool:
    model = _TARGET_MODELS[target_kind]
    return db.query(model.id).filter(model.id == target_id).first() is not None


@router.get("", response_model=CommentList)
def list_comments(
    target_kind: str = Query(...),
    target_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> CommentList:
    q = (
        db.query(Comment)
        .filter(Comment.target_kind == target_kind, Comment.target_id == target_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    )
    data = paginate(q, page=page, page_size=page_size)
    return CommentList(items=data["items"], total=data["total"])


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_password_changed),
) -> CommentOut:
    if not _target_exists(db, body.target_kind, body.target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target not found")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty text")
    row = Comment(
        target_kind=body.target_kind,
        target_id=body.target_id,
        author_id=user.id,
        author=user.full_name,
        role=_role_snapshot(user),
        text=text,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, body.target_kind, body.target_id, user, "Добавлен комментарий")
    return row


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    cid: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_password_changed),
) -> Response:
    row = db.query(Comment).filter(Comment.id == cid).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if row.author_id != user.id and not can(user, "admin", "view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    db.delete(row)
    db.commit()
    write_audit(db, row.target_kind, row.target_id, user, "Удалён комментарий")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Register in `backend/app/main.py`. Change the import line (line 3) from:

```python
from app.routers import auth, dashboard, dict, payments, procurement, reports, requests, search, support, users
```

to:

```python
from app.routers import auth, comments, dashboard, dict, history, payments, procurement, reports, requests, search, support, users
```

and add the include calls (after `app.include_router(search.router)`):

```python
app.include_router(comments.router)
app.include_router(history.router)
```

(Both `comments` and `history` are imported here; `history` is created in B3 — the import will resolve once B3 lands. If running tests after B2 but before B3, temporarily comment out the `history` import/include, or do B3 immediately after B2.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_comments.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/comments.py backend/app/schemas/comments.py backend/app/main.py backend/tests/test_comments.py
git commit -m "feat(comments): GET/POST/DELETE /comments — author snapshot, author|admin delete, audit (Phase 10 B2)"
```

---

## Task B3: History router (GET /history)

**Files:**
- Create: `backend/app/routers/history.py`
- Create: `backend/app/schemas/history.py`
- Modify: `backend/app/main.py` (the `history` import added in B2 now resolves)
- Test: `backend/tests/test_history.py`

**Interfaces:**
- Consumes: `AuditLog` (`entity_kind, entity_id, user_id, action, created_at`); `User.full_name`; `paginate`; `require_password_changed`.
- Produces: `GET /history?entity_kind=&entity_id=&page=&page_size=` → `HistoryList{items:AuditEntryOut[], total}` (desc). `AuditEntryOut = {id, action, actor, created_at}`; `actor` = `User.full_name` or `"Система"` when `user_id` is null.

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_history.py`.

```python
"""Tests for /history router (Phase 10 B3). Spec: docs/31 §7, docs/33 §2."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password
from app.models import AuditLog, User
from app.audit import write_audit

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"


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


def _admin_user(db):
    return db.query(User).filter_by(email=ADMIN_EMAIL).one()


def test_history_filtered_descending(client_admin, db_seeded):
    u = _admin_user(db_seeded)
    for action in ("первое", "второе", "третье"):
        write_audit(db_seeded, "procedure", 5, u, action)
    # unrelated entity
    write_audit(db_seeded, "procedure", 6, u, "чужей")
    r = client_admin.get("/history?entity_kind=procedure&entity_id=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert [a["action"] for a in body["items"]] == ["третье", "второе", "первое"]


def test_history_actor_resolved_and_system_fallback(client_admin, db_seeded):
    u = _admin_user(db_seeded)
    write_audit(db_seeded, "procedure", 7, u, "с автором")
    write_audit(db_seeded, "procedure", 7, None, "без автора")  # user_id=None
    body = client_admin.get("/history?entity_kind=procedure&entity_id=7").json()
    actors = {a["action"]: a["actor"] for a in body["items"]}
    assert actors["с автором"] == u.full_name
    assert actors["без автора"] == "Система"


def test_history_accepts_arbitrary_entity_kind(client_admin, db_seeded):
    u = _admin_user(db_seeded)
    write_audit(db_seeded, "dict", 1, u, "dict event")
    r = client_admin.get("/history?entity_kind=dict&entity_id=1")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_history_unauthenticated_401(client_seeded):
    assert client_seeded.get("/history?entity_kind=procedure&entity_id=1").status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_history.py -q`
Expected: FAIL — 404 (history router not registered; the import in main.py from B2 resolves only once `history.py` exists).

- [ ] **Step 3: Implement** — create `backend/app/schemas/history.py`:

```python
"""Pydantic schemas for /history (Phase 10 B3)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    actor: str
    created_at: str


class HistoryList(BaseModel):
    items: list[AuditEntryOut]
    total: int
```

Create `backend/app/routers/history.py`:

```python
"""/history router (Phase 10 B3) — «История» в карточках (audit_log, read-only).

Auth = require_password_changed. entity_kind не вайтлистится (свободный TEXT).
Актёр = User.full_name через batch-lookup; null user_id → «Система».
Spec: docs/31 §7, docs/33 §2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit import paginate
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import AuditLog, User
from app.schemas.history import AuditEntryOut, HistoryList

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryList)
def list_history(
    entity_kind: str = Query(...),
    entity_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> HistoryList:
    q = (
        db.query(AuditLog)
        .filter(AuditLog.entity_kind == entity_kind, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    data = paginate(q, page=page, page_size=page_size)
    items = data["items"]
    uids = {row.user_id for row in items if row.user_id is not None}
    names = {}
    if uids:
        names = {
            u.id: u.full_name
            for u in db.query(User.id, User.full_name).filter(User.id.in_(uids)).all()
        }
    out = [
        AuditEntryOut(
            id=row.id,
            action=row.action,
            actor=names.get(row.user_id, "Система"),
            created_at=row.created_at,
        )
        for row in items
    ]
    return HistoryList(items=out, total=data["total"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_history.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/history.py backend/app/schemas/history.py backend/tests/test_history.py
git commit -m "feat(history): GET /history audit read — newest-first, actor via User lookup (Phase 10 B3)"
```

---

## Task B4: Normalize audit `parent_request` → `parent`

**Files:**
- Modify: `backend/app/routers/requests.py` (the `write_audit(..., 'parent_request', ...)` call)
- Test: `backend/tests/test_requests.py` (append)

**Interfaces:**
- Consumes: `write_audit`.
- Produces: all parent-level audit rows use `entity_kind='parent'`, so `GET /history?entity_kind=parent&entity_id=…` (B3) is complete.

- [ ] **Step 1: Locate and write the failing test.** First find the call:

Run: `cd backend && grep -rn "parent_request" app/`
Expected: one or more hits in `app/routers/requests.py` (around line 743). Note the exact line.

Append to `backend/tests/test_requests.py` (adapt the trigger to whatever mutation at that line does — the test asserts the audit `entity_kind` is `'parent'`, not `'parent_request'`):

```python
def test_parent_mutation_audits_as_parent_kind(client_admin, db_seeded):
    """Regression (Phase 10 B4): parent-level audit must use entity_kind='parent'
    so /history?entity_kind=parent is complete (was 'parent_request')."""
    from app.models import AuditLog, ParentRequest
    # Trigger whichever parent mutation was previously logging 'parent_request'.
    # (If the located call is on create/cancel, drive that endpoint here; minimal
    # version: create a parent directly and call the same router path the bug was on.)
    parent = ParentRequest(code="Т-АУД", title="T", sostavitel="S")
    db_seeded.add(parent)
    db_seeded.commit()
    db_seeded.refresh(parent)
    # Exercise the cancelling path (status -> 'cancelled') which logs the parent.
    client_admin.post(f"/requests/{parent.id}/cancel")
    rows = db_seeded.query(AuditLog).filter_by(entity_id=parent.id).all()
    assert rows, "expected at least one audit row for the parent"
    assert all(r.entity_kind == "parent" for r in rows), (
        f"expected entity_kind='parent', got {[r.entity_kind for r in rows]}"
    )
```

> If the bug is on a different mutation (e.g. create/edit), replace the trigger lines above with that endpoint call. The assertion stays the same. The fixtures `client_admin`/`db_seeded` already exist in `test_requests.py` (mirror of `test_search.py`); if names differ there, reuse that file's existing authenticated fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && "$PY" -m pytest tests/test_requests.py::test_parent_mutation_audits_as_parent_kind -q`
Expected: FAIL — `entity_kind` is `'parent_request'`.

- [ ] **Step 3: Fix** — in `backend/app/routers/requests.py`, change the located `write_audit(...)` call's `'parent_request'` literal to `'parent'`. Single-word change; do not touch anything else.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && "$PY" -m pytest tests/test_requests.py -q`
Expected: PASS (whole file).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/requests.py backend/tests/test_requests.py
git commit -m "fix(audit): parent-level events use entity_kind='parent' (was 'parent_request') — completes /history (Phase 10 B4)"
```

---

## Task B5: backup.py + Alembic pre-migration hook

**Files:**
- Create: `backend/app/backup.py`
- Create: `scripts/backup.py`
- Modify: `backend/migrations/env.py`
- Test: `backend/tests/test_backup.py`
- Modify: `backend/.gitignore` (add `backups/`)

**Interfaces:**
- Consumes: `app.config.settings.DB_PATH`.
- Produces: `run_backup(db_path, backup_dir, keep=14) -> Path` (importable; used by `scripts/backup.py` and `migrations/env.py`). Creates `crm_YYYYMMDD_HHMMSS.db` via sqlite3 online-backup; prunes to newest `keep`.

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_backup.py`.

```python
"""Tests for app.backup.run_backup (Phase 10 B5). Spec: docs/33 §3/§9."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.backup import run_backup


def _make_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (x INTEGER)")
    con.execute("INSERT INTO t VALUES (42)")
    con.commit()
    con.close()


def test_run_backup_creates_valid_snapshot(tmp_path):
    src = tmp_path / "crm.db"
    _make_db(src)
    bdir = tmp_path / "backups"
    out = run_backup(str(src), str(bdir), keep=14)
    assert out.exists()
    assert out.suffix == ".db"
    # snapshot is a valid sqlite db with the data (online backup consistency)
    con = sqlite3.connect(str(out))
    rows = con.execute("SELECT x FROM t").fetchall()
    con.close()
    assert rows == [(42,)]


def test_run_backup_rotates_to_keep(tmp_path):
    src = tmp_path / "crm.db"
    _make_db(src)
    bdir = tmp_path / "backups"
    for _ in range(20):
        run_backup(str(src), str(bdir), keep=14)
    files = sorted(bdir.glob("*.db"))
    assert len(files) == 14  # pruned to newest 14


def test_run_backup_preserves_source(tmp_path):
    src = tmp_path / "crm.db"
    _make_db(src)
    run_backup(str(src), str(tmp_path / "b"), keep=14)
    # source still readable and intact
    con = sqlite3.connect(str(src))
    assert con.execute("SELECT x FROM t").fetchall() == [(42,)]
    con.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "$PY" -m pytest tests/test_backup.py -q`
Expected: FAIL — `ModuleNotFoundError: app.backup`.

- [ ] **Step 3: Implement** — create `backend/app/backup.py`:

```python
"""SQLite backup helper (Phase 10 B5). Spec: docs/33 §3/§9.

daily file backup of crm.db, retain last N (14). Uses sqlite3 online-backup
(conn.backup) for a consistent snapshot under concurrent writers — NOT a raw
file copy. Importable from migrations/env.py and scripts/backup.py.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def run_backup(db_path: str, backup_dir: str, keep: int = 14) -> Path:
    """Copy `db_path` to `backup_dir/crm_YYYYMMDD_HHMMSS.db` via online backup,
    then prune the directory to the newest `keep` files. Returns the new path.
    Raises on failure (§3: backup before migration is mandatory)."""
    src_path = Path(db_path)
    if not src_path.exists():
        raise FileNotFoundError(f"DB not found: {src_path}")

    bdir = Path(backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = bdir / f"crm_{stamp}.db"

    src = sqlite3.connect(str(src_path))
    dest = sqlite3.connect(str(dest_path))
    try:
        src.backup(dest)  # online, consistent snapshot
    finally:
        dest.close()
        src.close()

    # prune: keep newest `keep` by modification time
    files = sorted(bdir.glob("crm_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in files[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass

    return dest_path


__all__ = ["run_backup"]
```

Create `scripts/backup.py` (repo-root `scripts/`, thin CLI wrapper):

```python
"""CLI: daily SQLite backup of crm.db (Phase 10 B5). Run via cron/Task Scheduler.

Usage: python scripts/backup.py [--db crm.db] [--backup-dir backups] [--keep 14]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.backup import run_backup  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Backup CRM SQLite DB.")
    ap.add_argument("--db", default=settings.DB_PATH)
    default_dir = str(Path(settings.DB_PATH).resolve().parent / "backups")
    ap.add_argument("--backup-dir", default=default_dir)
    ap.add_argument("--keep", type=int, default=14)
    args = ap.parse_args()
    out = run_backup(args.db, args.backup_dir, keep=args.keep)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Modify `backend/migrations/env.py` — add the import after `from app.config import settings` (line 7):

```python
from app.backup import run_backup
```

and inside `run_migrations_online()`, immediately before `with connectable.connect() as connection:` (after the `event.listen(...)` line), insert the mandatory pre-migration backup:

```python
    # §3: обязательный бэкап перед миграциями. Кладём рядом с crm.db/backups.
    _backup_dir = str(Path(settings.DB_PATH).resolve().parent / "backups")
    run_backup(settings.DB_PATH, _backup_dir, keep=14)
```

Add `from pathlib import Path` to env.py's imports (top of file).

Add `backups/` to `backend/.gitignore`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && "$PY" -m pytest tests/test_backup.py -q`
Expected: PASS.

Run: `cd backend && "$PY" -m pytest -q` (full suite)
Expected: PASS — all backend tests green (search + comments + history + requests + backup + existing).

- [ ] **Step 5: Commit**

```bash
git add backend/app/backup.py scripts/backup.py backend/migrations/env.py backend/tests/test_backup.py backend/.gitignore
git commit -m "feat(backup): scripts/backup.py + app.backup.run_backup + Alembic pre-migration hook (Phase 10 B5)"
```

---

## ⏸ СТОП — ПРОВЕРКА (Фаза 10, backend)

- Команды:
  - `cd backend && "$PY" -m pytest -q` → **весь** набор PASS (436 базовых + новые test_search расширения + test_comments + test_history + test_backup + test_requests regression).
  - `grep -rn "parent_request" backend/app/` → **нет попаданий** (все нормализованы в `'parent'`).
- Человек: вручную (опционально) — `python scripts/backup.py` создаёт `backend/backups/crm_*.db`; проверить, что `GET /search?q=` отдаёт 5 групп, `POST /comments` + `GET /comments` + `DELETE /comments/{id}` работают под админом, `GET /history?entity_kind=procedure&entity_id=…` отдаёт события.
- **Жду подтверждения перед Фазой 10 frontend.**

---

## Self-Review (заполняется автором плана)

- **Spec coverage:** R1 (action-only) → B3 читает audit без schema-change ✓; R2 (search gap) → B1 ✓; R3–R7 (comments CRUD/author/audit) → B2 ✓; R8 (/history) → B3 ✓; R9 (parent_request) → B4 ✓; R13 (backup) → B5 ✓. R4 author snapshot → B2 `_role_snapshot` ✓. R14 (no migration) → ни одна задача не создаёт Alembic-ревизию ✓.
- **Placeholder scan:** нет TBD; весь код приведён дословно.
- **Type consistency:** `CommentOut`/`CommentList` (B2) и `AuditEntryOut`/`HistoryList` (B3) — имена стабильны; FE-план зеркалит их.
