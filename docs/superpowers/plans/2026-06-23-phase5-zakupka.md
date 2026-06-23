# Фаза 5 — «В закупке» (Zakupka) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Execute task-by-task with ⏸ review checkpoints between 5.1 / 5.2 / 5.3. Steps use `- [ ]` checkboxes.

**Goal:** Functional «В закупке» page — the procurement officer's workspace: list procedures (`block='zakupka'`, taken-to-work requests that left Комплектация), edit them in-place, split across suppliers with qty splitting, manage priced positions, advance working statuses, cancel/restore, and hand off to Сопровождение — with canonical design + static column widths.

**Architecture:** New backend procurement router (`/procurement`, `/procedures/{id}`, …) + Pydantic schemas mirroring the `requests` router; new frontend `Zakupka.tsx` page (sibling of `Komplektaciya.tsx`) + `RequestCard` extended to «mode Б1» (parametrized base path, sister-switcher, priced positions, split dialog). Reuses `DataTable` (static widths → `.reg.fixed`), `FilterBar`, `Chip`, `PositionTable`, react-query, cookie-auth `apiFetch`.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2 (backend, Python 3.12 base interpreter only); Vite 8 + React 19 + TS + React Router 7 + @tanstack/react-query 5 + vitest (node-env) (frontend).

## Global Constraints

- **Python interpreter:** Git Bash hard-codes `python` → MS Store stub. Use ABSOLUTE PATH `/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`. `backend/.venv` is EMPTY — never use it.
- **Money:** INTEGER kopecks in all API bodies; render via `format.money(kopecks)` → `1 234 567 ₽` (ru-RU, no decimals, space thousands). All sums include VAT. Numeric-only input.
- **Dates:** ISO `YYYY-MM-DD` in API; render via `format.dateRu` → `DD.MM.YY`. TZ Europe/Moscow, locale ru-RU.
- **RBAC:** reads = `require_password_changed` (any authed user); mutations = `require_action('zakupka','edit')` (Закупки employees + Куратор-Закупок + Админ; 403 otherwise).
- **Audit:** every mutating endpoint writes one `audit_log` row via `write_audit`.
- **Test DB:** `Base.metadata.create_all` + `seed_initial` (no migrations in tests). Seeded `dict` has the 6 `status_zakup` values.
- **Visual canon:** `frontend/src/styles/zakupki-crm.css` + `Concept design/index.html`. Zakupka block accent `--bc: var(--proc)` (orange). Status chip `.chip.proc.mini`; Отменена → `.chip.cancel` (line-through); null supplier → `.supp-c.empty` italic «не выбран».
- **React pitfalls (Phase-4 lessons — all apply to 5.3):** (1) no side-effects inside `setX(prev=>…)` updaters (StrictMode double-invokes); (2) `await invalidateQueries` BEFORE resetting derived state that re-seeds from `query.data`; (3) `?? false` for opt-in flags (never `?? true`); (4) no `queueMicrotask`+`setState` races.

## Decisions (confirmed / defaulted)

- **Scope:** Full Phase 5 (5.1 → 5.2 → 5.3), ⏸ between sub-tasks. List page is the first visible milestone. *(user-confirmed)*
- **Uncancel:** restores `status_zakup='Новая'` (no `status_zakup_prev` column / no migration). Faithful to «обратимо», mirrors `/requests` uncancel → `awaiting`. *(defaulted — override if you want prior-status restore)*
- **Route:** `/zakupka/:procedureId` (card loads procedure → tender → parent; sister-switcher navigates between procedure ids). *(defaulted)*
- **Column widths (sum 100):** `#`3 / Наим.20 / МТР8 / №заявки7 / №процедуры8 / Поставщик14 / ДатаЗагрузки9 / Нач.публ.9 / Заверш.публ.9 / Поз.5 / Статус8. *(defaulted)*
- **Filters MVP:** search + sort + «Показать отменённые» (spec §3 «по максимуму» deferred). *(defaulted)*
- **Inline-editable:** № заявки, № процедуры, Поставщик, Нач. публ., Заверш. публ., Статус. Actions Отменить/Передать в сопр. = card-only. Comments/История = disabled placeholders (Phase 10). `contract_sum` untouched; `block_entered_at` omitted from API; `page_size=100`. *(defaulted)*

---

## Sub-task 5.1 — Backend: чтение/правка процедур + статусы

**Files:**
- Create: `backend/app/schemas/procedures.py`
- Create: `backend/app/routers/procurement.py`
- Create: `backend/tests/test_procurement.py`
- Modify: `backend/app/main.py` (add `from app.routers import procurement` + `app.include_router(procurement.router)`)
- No DB migration (tests use `create_all`; no new columns).

**Produces (consumed by 5.2 / 5.3):**
- `ProcedureListItem`, `PaginatedProcedures`, `ProcedureDetail`, `ProcedurePatch`, `ProcedurePositionOut` (schemas).
- Endpoints: `GET /procurement`, `GET /procedures/{id}`, `PATCH /procedures/{id}`, `POST /procedures/{id}/cancel`, `POST /procedures/{id}/uncancel`.

### Schemas (`schemas/procedures.py`)

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


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
    price: Optional[int] = None  # INTEGER kopecks


class ProcedureListItem(BaseModel):
    id: int
    proc: Optional[str] = None
    tender_num: Optional[str] = None     # tender.num (№ заявки)
    code: str                            # parent.code (Т-67)
    title: str                           # parent.title
    mtr: Optional[str] = None            # proc.mtr ?? parent.mtr
    supplier: Optional[str] = None
    fio_zakupshchik: Optional[str] = None
    pub_start: Optional[str] = None
    pub_end: Optional[str] = None
    zagruzka: str                        # parent.zagruzka
    position_count: int
    status_zakup: Optional[str] = None
    created_at: str


class PaginatedProcedures(BaseModel):
    items: list[ProcedureListItem]
    total: int


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
    created_at: str
    positions: list[ProcedurePositionOut] = []
    # NOTE: block_entered_at intentionally OMITTED (служебное)


class ProcedurePatch(BaseModel):
    proc: Optional[str] = None
    tender_num: Optional[str] = None     # writes tender.num
    supplier: Optional[str] = None
    fio_zakupshchik: Optional[str] = None
    mtr: Optional[str] = None
    pub_start: Optional[str] = None
    pub_end: Optional[str] = None
    status_zakup: Optional[str] = None   # validated against dict (6 values)
```

### Endpoint contracts (`routers/procurement.py`)

- **`GET /procurement`** → `PaginatedProcedures`. Query: `include_archived: bool=False`, `search: Optional[str]`, `sort: str='created_at'` (whitelist `created_at|code|num|proc|supplier|status|mtr|zagruzka|pub_start|pub_end`), `page: int≥1`, `page_size: int=50 (1..200)`. Dep `require_password_changed`.
  - Base: `Procedure.block=='zakupka'`. Active default excludes `status_zakup=='Отменена'` but INCLUDES NULL (`or_(status_zakup.is_(None), status_zakup!='Отменена')`). `include_archived=1` shows all.
  - Join `Tender` + `ParentRequest` for search/sort. Search (Unicode `py_casefold` + `instr`) across `proc`, `tender.num`, `supplier`, `parent.code`, `parent.title`.
  - `paginate(q, page, page_size)` then per-row `position_count = COUNT(ProcedurePosition WHERE procedure_id=proc.id)`. Build `ProcedureListItem` with `mtr = proc.mtr or parent.mtr`.
- **`GET /procedures/{id}`** → `ProcedureDetail` (404 if missing). Dep `require_password_changed`. Includes positions (asc id) with `price`.
- **`PATCH /procedures/{id}`** → `ProcedureDetail`. Body `ProcedurePatch`. Dep `require_action('zakupka','edit')`. 404 if missing.
  - Apply `proc/supplier/fio_zakupshchik/mtr/pub_start/pub_end` onto Procedure (`exclude_unset`).
  - `tender_num` → `proc.tender.num`. Unique `proc` (non-null) → 409 `"proc already exists"`; unique `tender.num` (non-null) → 409 `"tender num already exists"`. Multiple NULLs allowed (SQLite UNIQUE treats NULLs as distinct).
  - `status_zakup`: load dict values `kind='status_zakup'` → if PATCH value not in set → **422** `"invalid status_zakup"`. (This naturally rejects `Новая`/`Отменена` — service-only.)
  - audit `entity_kind='procedure'`, `action='update'`.
- **`POST /procedures/{id}/cancel`** → `ProcedureDetail`. Dep `require_action('zakupka','edit')`. 404 if missing. 409 if already `status_zakup=='Отменена'`. Sets `status_zakup='Отменена'`. audit `action='cancel'`.
- **`POST /procedures/{id}/uncancel`** → `ProcedureDetail`. Dep `require_action('zakupka','edit')`. 404 if missing. 409 if `status_zakup!='Отменена'`. Sets `status_zakup='Новая'`. audit `action='uncancel'`.

### Test behaviors (`tests/test_procurement.py`)

Mirror `test_requests.py` fixtures: `db_seeded`, `client_seeded`, `client_admin`, plus `_make_zakup_emp` (Закупки employee, has `zakupka` edit) and `_make_kompl_emp` (no `zakupka` edit, RBAC negative). Helper `_take_to_work(client, parent_id)` → returns `{tender_id, procedure_id}` (create parent w/ positions, POST `/requests/{id}/take-to-work`).

- [ ] 1. `GET /procurement` empty → `{items:[], total:0}`.
- [ ] 2. After take-to-work → exactly 1 item; fields: `proc=None`, `tender_num=None`, `code`/`title` from parent, `mtr` falls back to parent.mtr, `supplier=None`, `status_zakup='Новая'`, `position_count` = #positions.
- [ ] 3. A `block='soprovozhdenie'` procedure (set directly on the row) is NOT listed.
- [ ] 4. `status_zakup='Отменена'` hidden by default, present with `?include_archived=1`.
- [ ] 5. `status_zakup='Новая'` IS in the active list.
- [ ] 6. Search matches `code`/`tender.num`/`proc`/`supplier`/`title`; non-match returns 0.
- [ ] 7. Each sort key orders rows; invalid sort falls back to default (no 500).
- [ ] 8. `total` correct across pages; `page=2` returns second slice.
- [ ] 9. Null `proc`/`tender_num`/`supplier` do not crash (serialize as null).
- [ ] 10. `GET /procedures/{id}` 200 with detail + `positions[*].price`; 404 unknown.
- [ ] 11. `PATCH` `proc`/`supplier`/`mtr`/`pub_start`/`pub_end`/`fio_zakupshchik` persist; `tender_num` updates `tender.num`.
- [ ] 12. `PATCH status_zakup` with each of 6 dict values → 200; with garbage → 422; with `'Новая'` → 422; with `'Отменена'` → 422.
- [ ] 13. `PATCH` duplicate non-null `proc` → 409; duplicate non-null `tender_num` → 409; NULL `proc`/`tender_num` on multiple rows → allowed.
- [ ] 14. `PATCH` 404 unknown id.
- [ ] 15. `cancel` → `status_zakup='Отменена'` + audit; cancel again → 409; `uncancel` → `status_zakup='Новая'` + audit; uncancel when not cancelled → 409; block stays `'zakupka'` throughout.
- [ ] 16. RBAC: `_make_kompl_emp` PATCH/cancel/uncancel → 403; GET list + GET detail → 200.

### Commands

- Red→green loop: `cd backend && "$PY" -m pytest tests/test_procurement.py -v` (`PY=/c/Users/ken29/AppData/Local/Programs/Python/Python312/python.exe`).
- No regressions: `cd backend && "$PY" -m pytest -q`.
- Commits per endpoint group (schemas+list, detail+patch, cancel/uncancel, tests).

**→ ⏸ STOP after 5.1.** Verify: `pytest test_procurement.py -v` all pass + full suite green. Report endpoint shapes to lock before 5.2/5.3 consume them.

---

## Sub-task 5.2 — Backend: разбиение + позиции с ценой + to-support  *(roadmap — expand at ⏸ gate)*

**Files:** modify `routers/procurement.py`, `schemas/procedures.py`, `tests/test_procurement.py`.

**Produces:** `SplitIn`, `ProcedurePositionIn`, `ProcedurePositionPatch` (schemas); endpoints `POST /procedures/{id}/split`, `GET|POST|PATCH|DELETE /procedures/{id}/positions`, `POST /procedures/{id}/to-support`.

**Key invariants:**
- `split {positions:[{source_position_id, qty}], supplier?}` → new Procedure (same `tender_id`, `block='zakupka'`, `proc=None`, `status_zakup='Новая'`, `block_entered_at=now`); transfers named positions (qty=transferred) from source → sister. **Σ qty per `source_id` across ALL procedures ≤ `requested_position.qty`** → else **422**. Check is server-side, cross-procedure, atomic with the insert.
- `/positions` CRUD: `price` INTEGER kopecks (nullable); mass insert; `source_id=null` for purchaser-added; copy-row.
- `to-support`: only from `status_zakup=='На сделку'` → `block='soprovozhdenie'`, `status_postavki='Новая'`, `block_entered_at=now ISO UTC`; else **409**. Verify `procedure_status_postavki_check` accepts `'Новая'` (it does — models.py:182-187). Procedure leaves `/procurement` active list.

**Test behaviors:** split happy-path (sister appears in list, source qty decremented), invariant 422 (single + cumulative), positions price CRUD, to-support 200/409 matrix, RBAC 403, audit.

**→ ⏸ STOP after 5.2.** Verify: `pytest` (split invariant + to-support 409 are the critical ones).

---

## Sub-task 5.3 — Frontend: страница «В закупке» + карточка (режим Б1)  *(roadmap — expand at ⏸ gate)*

**Files:** create `frontend/src/api/procedures.ts`, `frontend/src/pages/Zakupka.tsx`; modify `frontend/src/cards/RequestCard.tsx` (mode Б1), `frontend/src/App.tsx` (replace `PlaceholderPage` at `:32`, add `/zakupka/:id`), `frontend/src/components/Tabs.tsx` (wire zakupka counter), possibly `frontend/src/components/PositionTable.tsx` (price column config — prefer a column-set prop over forking, to protect mode-A regression).

**Produces:** typed API client; Zakupka list page; RequestCard mode Б1 (parametrized `basePath` so mode A `/komplektaciya` still works — highest regression risk).

**List page:** react-query key `['procurements', {search, include_archived, sort}]`; `DataTable` 11 cols with the width split (→ `.reg.fixed`); `FilterBar` (search + sort select + «Показать отменённые»); status chip `.proc.mini` (`.cancel` for Отменена); `.supp-c.empty` «не выбран» for null supplier; inline optimistic PATCH on the 6 editable fields + `savedTick` counter banner (pitfall #1: pure cache write, fetch from handler; pitfall #2: `await invalidateQueries` before reset; pitfall #3: `?? false`); row-click → `/zakupka/{id}`; EmptyState; «+ Заявка» disabled stub; «Экспорт».

**Card Б1:** header № заявки/№ процедуры/поставщик/ФИО закупщика; sister-switcher `.sib` (lists all procedures of the tender; switching = navigate procedure id — pitfall #4: scope state by procedure id, no microtask); priced positions via PositionTable (+price column, `format.money`); split dialog (select positions + qty → `splitProcedure` → invalidate `['procurements']`); «Передать в сопровождение» disabled unless `status_zakup==='На сделку'`; cancel/uncancel; back → `/zakupka` (parametrized). Comments/История = disabled placeholders.

**Verify:** `vitest run` (+ new tests; mode-A regression), `tsc --noEmit`, `npm run build`, Playwright ui-checker vs `Concept design/index.html #view-zakup`.

**→ ⏸ final STOP.** Human end-to-end: take-to-work → appears in В закупке → edit fields/prices → split 2 suppliers → advance to «На сделку» → «Передать в сопровождение» → leaves block; sisters independent.

---

## Risks (cross-cutting)

- **Split Σ≤requested invariant (5.2):** server-side, cross-procedure, atomic → 422. Critical correctness rule.
- **status_zakup branches (5.1):** accept 6 dict via PATCH; reject Новая/Отменена via PATCH (service-only); list/chip MUST still display Новая/Отменена; dropdown omits service values.
- **position_count cartesian (5.1):** correlated scalar subquery per procedure, not a join — else inflated counts.
- **RequestCard shared-component regression (5.3):** parametrize `basePath`; keep mode-A tests green.
- **Money 100× errors (5.3):** integer kopecks end-to-end; `format.money` only at render.
