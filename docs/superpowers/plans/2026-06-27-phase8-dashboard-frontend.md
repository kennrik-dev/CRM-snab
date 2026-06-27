# Phase 8 «Дашборд» — Frontend 8.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the «Дашборд» FE — 6 meters, 4-stage flow, 2-tier «Требует внимания», 20-item «Лента событий», 3 compact tables — over the already-shipped Phase 8.1 `GET /dashboard` backend. Replaces the `/dashboard` placeholder; remains the default landing route (`/` → `/dashboard`).

**Architecture:** Mirror the established patterns: a new `api/dashboard.ts` (twin of `api/payments.ts`); a pure `lib/dashView.ts` (`relTime`, `targetRoute`, `feedRoute`) with vitest; a new `pages/Dashboard.tsx` with presentational sub-components (`Meters`, `FlowRail`, `AttentionPanel`, `FeedPanel`, `CompactTables`) driven by ONE `useQuery(['dashboard'])` (60 s `refetchInterval` + `refetchOnWindowFocus`); `App.tsx` route swap. **No CSS** is added — every class used already exists in `frontend/src/styles/zakupki-crm.css` (`.meters/.meter/.ml/.mv/.seg/.ms/.flowrail/.fstage/.ft/.fn/.fs/.grid2/.panel/.phead/.cnt/.alert/.aid/.at/.ab/.fitem/.ft2/.eyebrow/.block/.block-h/.bnum/.btitle/.beng/.bcount/.blink/.tbl-scroll/.reg/.fit/.ovd/.prog`, responsive `@media` for `.meters` 3/2 cols). RBAC: none (read-only, identical for all roles).

**Tech Stack:** React 19, Vite, TypeScript (strict), @tanstack/react-query v5, react-router-dom, Vitest (node env). Backend: the Phase 8.1 `/dashboard` router.

**Design spec:** `docs/superpowers/specs/2026-06-27-phase8-dashboard-design.md` (authoritative). Backend plan: `docs/superpowers/plans/2026-06-27-phase8-dashboard-backend.md` (prerequisite). Canonical visuals: `Concept design/index.html` (`#view-dash`, lines 34–45) + `Concept design/zakupki-crm.js` (`rMeters/rFlow/rAlerts/rFeed/rDash`, `tblAwaitingC/tblProcC/tblSuppC`).

## Global Constraints

- **Money = INTEGER kopecks** end-to-end; render via `money()` from `lib/format.ts` (meter `amount`, support-table `contract_sum` are kopecks). Dates ISO; render via `dateRu()`.
- **API:** every call through `apiFetch` in `api/client.ts` (`/api` prefix, `credentials:'include'`, 401→`auth:logout`). Mirror `api/payments.ts`.
- **One query:** `useQuery({ queryKey: ['dashboard'], queryFn: getDashboard, refetchInterval: 60000, refetchOnWindowFocus: true })` — overrides the app default (`refetchOnWindowFocus:false`). Sub-components are **presentational** (receive their slice as props); they do NOT call `useQuery`.
- **Meter `color`** is the bare CSS token suffix the BE sends (`'proc'|'supp'|'ok'|'late'|'pay'|'wait'`); render `style={{ '--c': \`var(${m.color})\` }}`. Alert severity → `--al`: error→`var(--late)`, warning→`var(--proc)`.
- **seg-bar:** render `m.seg.total` `<span>`s, the first `m.seg.on` get class `on`.
- **Navigation:** flow stage → its `route`; attention «Открыть» → `targetRoute(target)`; compact row → card route; compact «Открыть раздел →» → the page route. Feed items are clickable only for `parent`/`payment` targets (`feedRoute`); procedure feed targets are **not** links (block is unknown → can't pick zakupka vs soprovozhdenie card).
- **«#» ordinal omitted** in compact tables (`DataTable` has no row-index in `render`); columns match the concept otherwise.
- **No CSS changes.** If a class looks missing, re-read `styles/zakupki-crm.css:53-87` — it is there.
- **TDD where there is logic:** pure helpers (`relTime`, `targetRoute`, `feedRoute`) get vitest (red→green→commit). Components verified by `npx tsc -b` + the `ui-checker` Playwright agent at ⏸ stops (Phase 4/6.3/7.2 rhythm).
- **Commit prefix:** `feat(dashboard):` (or `test(dashboard):` for the pure-helper task). One commit per task.
- **Verify commands** (from `frontend/`): type-check `npx tsc -b`; tests `npm test`; lint `npm run lint`; build `npm run build`. Visual checks need `npm run dev` + backend on `:8000` with data.
- **Don't break the dev environment:** keep `crm.db`, uvicorn (`:8000`), vite healthy.

## File Structure

- **Create** `frontend/src/api/dashboard.ts` — types + `getDashboard()` (twin of `api/payments.ts`).
- **Create** `frontend/src/lib/dashView.ts` — pure `relTime`, `targetRoute`, `feedRoute`.
- **Create** `frontend/src/lib/dashView.test.ts` — vitest for the three helpers.
- **Create** `frontend/src/pages/Dashboard.tsx` — the page + presentational sub-components (`Meters`, `FlowRail`, `AttentionPanel`, `FeedPanel`, `CompactTables`).
- **Modify** `frontend/src/App.tsx` — `/dashboard` → `<Dashboard/>`.

Decomposition: pure helpers first (T1, unit-tested in isolation); api module (T2); then the page grows zone-by-zone (T3 meters+flow → T4 panels → T5 compact tables), each a reviewer gate ending in `tsc -b` + ui-checker.

---

## Task 1: Pure helpers — `relTime` + `targetRoute` + `feedRoute` (TDD)

**Files:**
- Create: `frontend/src/lib/dashView.ts`
- Create: `frontend/src/lib/dashView.test.ts`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `relTime(iso: string, now: Date = new Date()): string` — «только что» / «N мин назад» / «N ч назад» / «вчера» / «N дн назад» / `DD.MM.YY` (≥30 d) / `—` (unparseable/future).
  - `targetRoute(t: { kind: string; id: number } | null | undefined): string | null` — parent→`/komplektaciya/:id`, procedure→`/soprovozhdenie/:id`, payment→`/oplaty/:id`, else null. (Used by attention — its procedures are always support-stage.)
  - `feedRoute(t: { kind: string; id: number } | null | undefined): string | null` — `targetRoute` but **only for parent/payment** (procedure excluded — unknown block).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/dashView.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { relTime, targetRoute, feedRoute } from './dashView'

const NOW = new Date('2026-06-27T12:00:00')

describe('relTime', () => {
  it('just now / minutes / hours', () => {
    expect(relTime('2026-06-27T11:59:30', NOW)).toBe('только что')
    expect(relTime('2026-06-27T11:55:00', NOW)).toBe('5 мин назад')
    expect(relTime('2026-06-27T10:00:00', NOW)).toBe('2 ч назад')
  })
  it('вчера / N дней', () => {
    expect(relTime('2026-06-26T10:00:00', NOW)).toBe('вчера')
    expect(relTime('2026-06-24T10:00:00', NOW)).toBe('3 дн назад')
  })
  it('older → DD.MM.YY', () => {
    expect(relTime('2026-05-20T10:00:00', NOW)).toBe('20.05.26')
  })
  it('unparseable / future → —', () => {
    expect(relTime('not-a-date', NOW)).toBe('—')
    expect(relTime('2026-06-28T10:00:00', NOW)).toBe('—')
  })
})

describe('targetRoute', () => {
  it('maps kinds to card routes', () => {
    expect(targetRoute({ kind: 'parent', id: 5 })).toBe('/komplektaciya/5')
    expect(targetRoute({ kind: 'procedure', id: 7 })).toBe('/soprovozhdenie/7')
    expect(targetRoute({ kind: 'payment', id: 9 })).toBe('/oplaty/9')
  })
  it('null/unknown → null', () => {
    expect(targetRoute(null)).toBeNull()
    expect(targetRoute({ kind: 'dict', id: 1 })).toBeNull()
  })
})

describe('feedRoute', () => {
  it('links parent & payment only', () => {
    expect(feedRoute({ kind: 'parent', id: 5 })).toBe('/komplektaciya/5')
    expect(feedRoute({ kind: 'payment', id: 9 })).toBe('/oplaty/9')
  })
  it('procedure → null (block unknown)', () => {
    expect(feedRoute({ kind: 'procedure', id: 7 })).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- dashView.test.ts`
Expected: FAIL — module `./dashView` not found.

- [ ] **Step 3: Implement `frontend/src/lib/dashView.ts`**

```typescript
/**
 * Pure view helpers for the «Дашборд» page.
 *
 * relTime: ISO datetime → human relative label (ru), computed client-side.
 *   now is injectable for tests.
 * targetRoute: attention target → card route (attention procedures are always
 *   support-stage, so procedure → /soprovozhdenie/:id is correct there).
 * feedRoute: feed target → route ONLY for parent/payment; a feed procedure's
 *   block is unknown, so it is not made a link.
 */

export function relTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  const t = then.getTime()
  if (isNaN(t)) return '—'
  const diffMs = now.getTime() - t
  if (diffMs < 0) return '—'
  const min = Math.floor(diffMs / 60000)
  if (min < 1) return 'только что'
  if (min < 60) return `${min} мин назад`
  const hours = Math.floor(min / 60)
  if (hours < 24) return `${hours} ч назад`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'вчера'
  if (days < 30) return `${days} дн назад`
  const d = String(then.getDate()).padStart(2, '0')
  const mo = String(then.getMonth() + 1).padStart(2, '0')
  const y = String(then.getFullYear()).slice(2)
  return `${d}.${mo}.${y}`
}

export function targetRoute(
  t: { kind: string; id: number } | null | undefined,
): string | null {
  if (!t) return null
  switch (t.kind) {
    case 'parent':
      return `/komplektaciya/${t.id}`
    case 'procedure':
      return `/soprovozhdenie/${t.id}`
    case 'payment':
      return `/oplaty/${t.id}`
    default:
      return null
  }
}

export function feedRoute(
  t: { kind: string; id: number } | null | undefined,
): string | null {
  if (!t) return null
  if (t.kind === 'parent' || t.kind === 'payment') return targetRoute(t)
  return null
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- dashView.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/dashView.ts frontend/src/lib/dashView.test.ts
git commit -m "test(dashboard): relTime + targetRoute + feedRoute pure helpers (Phase 8.2 T1)"
```

---

## Task 2: `api/dashboard.ts` (types + endpoint)

**Files:**
- Create: `frontend/src/api/dashboard.ts`

**Interfaces:**
- Consumes: `apiFetch` from `api/client.ts`.
- Produces: types `Target`, `SegBar`, `Meter`, `FlowStage`, `AttentionItem`, `FeedItem`, `AwaitingRow`, `ProcurementRow`, `SupportRow`, `CompactTable`, `DashboardTables`, `DashboardData`; function `getDashboard()`. These match the Phase 8.1 backend schemas verbatim (`backend/app/schemas/dashboard.py`).

> No vitest here — types + one thin `apiFetch` wrapper, no new runtime logic. Gate is `tsc -b` green.

- [ ] **Step 1: Write `frontend/src/api/dashboard.ts`**

```typescript
import { apiFetch } from './client'

// Зеркало backend schemas/dashboard.py (Фаза 8.1). Деньги — int копейки,
// даты — ISO строки (Optional). Метры: amount — коп. (FE форматирует money()).

export type Target = { kind: string; id: number }

export type SegBar = { on: number; total: number }

export type Meter = {
  key: string
  label: string
  value: number
  unit: string | null
  sub: string | null // text detail (e.g. "34 / 39 поставок")
  amount: number | null // kopecks; rendered via money() when sub is null
  seg: SegBar
  color: string // bare token, e.g. 'proc' → rendered as var(--proc)
}

export type FlowStage = {
  key: string
  label: string
  count: number
  sub: string | null
  route: string
  color: string
}

export type AttentionItem = {
  id_label: string
  severity: string // 'error' | 'warning'
  text: string
  target: Target
}

export type FeedItem = {
  actor: string
  action_label: string
  entity_display: string | null
  target: Target | null
  created_at: string
}

export type AwaitingRow = {
  id: number
  code: string
  title: string
  mtr: string | null
  srok: string | null
  position_count: number
  status: string
}

export type ProcurementRow = {
  id: number
  code: string
  title: string
  num: string | null
  supplier: string | null
  position_count: number
  status_zakup: string | null
}

export type SupportRow = {
  id: number
  code: string
  title: string
  num: string | null
  supplier: string | null
  contract_sum: number | null
  status_postavki: string | null
  overdue_pct: number
  delivered: number
  total: number
}

export type CompactTable<R> = { total: number; items: R[] }

export type DashboardTables = {
  awaiting: CompactTable<AwaitingRow>
  procurement: CompactTable<ProcurementRow>
  support: CompactTable<SupportRow>
}

export type DashboardData = {
  meters: Meter[]
  flow: FlowStage[]
  attention: AttentionItem[]
  feed: FeedItem[]
  tables: DashboardTables
}

// ---- Endpoint ------------------------------------------------------------

export function getDashboard(): Promise<DashboardData> {
  return apiFetch<DashboardData>('/dashboard')
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/dashboard.ts
git commit -m "feat(dashboard): api/dashboard.ts types + endpoint (Phase 8.2 T2)"
```

---

## Task 3: `pages/Dashboard.tsx` — meters + flow + route + refresh

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx` (import `Dashboard`; swap the `/dashboard` placeholder)

**Interfaces:**
- Consumes: `getDashboard`, types from `api/dashboard.ts`; `money` from `lib/format.ts`; `useNavigate`.
- Produces: exported `Dashboard` component mounted at `/dashboard`. This task renders the meters strip + flow rail (panels/tables land in T4/T5).

- [ ] **Step 1: Write `frontend/src/pages/Dashboard.tsx` (meters + flow)**

```typescript
import { type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDashboard, type Meter, type FlowStage } from '../api/dashboard'
import { money } from '../lib/format'

function Meters({ data }: { data: Meter[] }) {
  return (
    <div className="meters">
      {data.map((m) => (
        <div key={m.key} className="meter" style={{ '--c': `var(${m.color})` } as CSSProperties}>
          <div className="ml">
            <i />
            {m.label}
          </div>
          <div className="mv">
            {m.value}
            {m.unit ? <em>{m.unit}</em> : null}
          </div>
          <div className="seg">
            {Array.from({ length: m.seg.total }, (_, i) => (
              <span key={i} className={i < m.seg.on ? 'on' : ''} />
            ))}
          </div>
          <div className="ms">{m.amount != null ? <b>{money(m.amount)}</b> : (m.sub ?? '')}</div>
        </div>
      ))}
    </div>
  )
}

function FlowRail({ data, onGo }: { data: FlowStage[]; onGo: (route: string) => void }) {
  return (
    <div className="flowrail">
      {data.map((s) => (
        <div
          key={s.key}
          className="fstage"
          style={{ '--c': `var(${s.color})` } as CSSProperties}
          onClick={() => onGo(s.route)}
        >
          <div className="ft">
            <i />
            <span>{s.label}</span>
          </div>
          <div className="fn">{s.count}</div>
          <div className="fs">{s.sub ?? ' '}</div>
        </div>
      ))}
    </div>
  )
}

export function Dashboard() {
  const navigate = useNavigate()
  const q = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    refetchInterval: 60000,
    refetchOnWindowFocus: true,
  })

  if (q.isError) {
    return (
      <div className="wrap">
        <div className="page-h">
          <h1>Дашборд</h1>
          <span className="desc">не удалось загрузить показатели</span>
          <span className="sp" />
        </div>
      </div>
    )
  }

  // Loading skeleton (full page) — keeps the layout from jumping and lets the
  // data branch below use `d` without null-checks.
  if (!q.data) {
    return (
      <div className="wrap">
        <div className="eyebrow" style={{ margin: '0 0 10px' }}>
          Показатели · реальное время
        </div>
        <div className="meters">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="meter" style={{ '--c': 'var(--line)' } as CSSProperties}>
              <div className="ml">…</div>
              <div className="mv">…</div>
              <div className="seg">
                {Array.from({ length: 14 }, (_, j) => (
                  <span key={j} />
                ))}
              </div>
              <div className="ms">…</div>
            </div>
          ))}
        </div>
        <div className="eyebrow" style={{ margin: '6px 0 10px' }}>
          Поток по этапам
        </div>
        <div className="flowrail" />
      </div>
    )
  }

  const d = q.data
  return (
    <div className="wrap">
      <div className="eyebrow" style={{ margin: '0 0 10px' }}>
        Показатели · реальное время
      </div>
      <Meters data={d.meters} />

      <div className="eyebrow" style={{ margin: '6px 0 10px' }}>
        Поток по этапам
      </div>
      <FlowRail data={d.flow} onGo={(route) => navigate(route)} />

      {/* Требует внимания / Лента событий — Task 4 */}
      {/* Компактные таблицы — Task 5 */}
    </div>
  )
}
```

- [ ] **Step 2: Wire the route in `frontend/src/App.tsx`**

Add the import (with the other page imports, alphabetical-ish after the cards):

```typescript
import { Dashboard } from './pages/Dashboard'
```

Replace the `/dashboard` placeholder route:

```typescript
        <Route path="/dashboard" element={<Dashboard />} />
```

(`PlaceholderPage` stays — it is still used for `/otchety`. The `/` → `/dashboard` redirect is unchanged.)

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 4: Visual verify (⏸ — requires backend on :8000 + dev data)**

With `cd frontend && npm run dev` + backend running, sign in as admin; `/` lands on `/dashboard`. Expect: 6 meter cards (`.meters`) with value + unit + 14-dot seg + sub/money; a flow rail (`.flowrail`) of 4 stages with arrow separators; clicking a stage navigates to its page. Numbers match the backend. Dispatch `ui-checker` vs `Concept design/index.html` `#view-dash` (top portion); confirm no console errors / failed requests, desktop ≥1280px.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx frontend/src/App.tsx
git commit -m "feat(dashboard): Dashboard page — meters + flow rail (Phase 8.2 T3)"
```

---

## Task 4: «Требует внимания» + «Лента событий» panels

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` (add `AttentionPanel`, `FeedPanel`; render the `.grid2`)

**Interfaces:**
- Consumes: `AttentionItem`, `FeedItem`, `Target` from `api/dashboard.ts`; `relTime`, `targetRoute`, `feedRoute` from `lib/dashView.ts`.
- Produces: the two-panel `.grid2`. Attention: red errors / amber warnings, top-20 + «и ещё N», header count = true total; «Открыть» → `targetRoute`. Feed: `.fitem` rows, clickable only for parent/payment targets.

- [ ] **Step 1: Extend imports in `Dashboard.tsx`**

Change the `api/dashboard` and add `dashView` imports. Replace:

```typescript
import { getDashboard, type Meter, type FlowStage } from '../api/dashboard'
import { money } from '../lib/format'
```

with:

```typescript
import {
  getDashboard,
  type Meter,
  type FlowStage,
  type AttentionItem,
  type FeedItem,
} from '../api/dashboard'
import { relTime, targetRoute, feedRoute } from '../lib/dashView'
import { money } from '../lib/format'
```

- [ ] **Step 2: Add the two panel sub-components (above `export function Dashboard()`)**

```typescript
function AttentionPanel({
  data,
  onOpen,
}: {
  data: AttentionItem[]
  onOpen: (route: string) => void
}) {
  const shown = data.slice(0, 20)
  const rest = data.length - shown.length
  return (
    <div className="panel">
      <div className="phead">
        <h2>Требует внимания</h2>
        <span className="cnt">{data.length}</span>
        <span className="sp" />
      </div>
      {shown.length === 0 ? (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          Всё под контролем
        </div>
      ) : (
        shown.map((a, i) => {
          const route = targetRoute(a.target)
          return (
            <div
              key={i}
              className="alert"
              style={{
                '--al': `var(${a.severity === 'error' ? 'late' : 'proc'})`,
              } as CSSProperties}
            >
              <span className="aid">{a.id_label}</span>
              <span className="at">{a.text}</span>
              <button
                className="ab"
                disabled={!route}
                onClick={() => route && onOpen(route)}
              >
                Открыть
              </button>
            </div>
          )
        })
      )}
      {rest > 0 && (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          и ещё {rest}
        </div>
      )}
    </div>
  )
}

function FeedPanel({
  data,
  onOpen,
}: {
  data: FeedItem[]
  onOpen: (route: string) => void
}) {
  return (
    <div className="panel">
      <div className="phead">
        <h2>Лента событий</h2>
        <span className="sp" />
      </div>
      {data.length === 0 ? (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          Пока нет событий
        </div>
      ) : (
        data.map((f, i) => {
          const route = feedRoute(f.target)
          return (
            <div
              key={i}
              className="fitem"
              style={route ? { cursor: 'pointer' } : undefined}
              onClick={route ? () => onOpen(route) : undefined}
            >
              <span className="ft2">{relTime(f.created_at)}</span>
              <div>
                <b>{f.actor}</b>{' '}
                <span>
                  {f.action_label}
                  {f.entity_display ? ` ${f.entity_display}` : ''}
                </span>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
```

- [ ] **Step 3: Render the `.grid2` in `Dashboard()`**

Replace the `{/* Требует внимания / Лента событий — Task 4 */}` placeholder with:

```typescript
      <div className="grid2">
        <AttentionPanel
          data={d.attention}
          onOpen={(route) => navigate(route)}
        />
        <FeedPanel data={d.feed} onOpen={(route) => navigate(route)} />
      </div>
```

(This sits between the `FlowRail` block and the `{/* Компактные таблицы — Task 5 */}` comment.)

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 5: Visual verify (⏸)**

On `/dashboard`: the `.grid2` shows two panels. «Требует внимания» lists red errors (overdue delivery/payment, missing docs) above amber warnings (УПД без сертификата), header badge = total, top-20 + «и ещё N» when more; «Открыть» opens the right card. «Лента событий» shows newest-first items with actor + action + entity + relative time; parent/payment items are clickable. Dispatch `ui-checker`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(dashboard): Требует внимания + Лента событий panels (Phase 8.2 T4)"
```

---

## Task 5: Compact tables (awaiting / procurement / support) + full verify

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` (add `CompactTables`; render the 3 `.block`s)

**Interfaces:**
- Consumes: `DashboardTables`, `AwaitingRow`, `ProcurementRow`, `SupportRow` from `api/dashboard.ts`; `DataTable`/`DataTableColumn`; `money`/`dateRu`; `postavkiStatusChip`/`procStatusChip` from `lib/statusColors.ts`; `Chip`.
- Produces: 3 `.block` tables (top-10 rows, true total in `.bcount`, «Открыть раздел →» → page; row click → card). Columns per spec §8 (no «#» ordinal).

- [ ] **Step 1: Extend imports in `Dashboard.tsx`**

First, change the top `react` import (from Task 3) to also pull `ReactNode`:

```typescript
import { type CSSProperties, type ReactNode } from 'react'
```

Then replace the `api/dashboard` import block (from Task 4) with:

```typescript
import {
  getDashboard,
  type Meter,
  type FlowStage,
  type AttentionItem,
  type FeedItem,
  type DashboardTables,
  type AwaitingRow,
  type ProcurementRow,
  type SupportRow,
} from '../api/dashboard'
import { relTime, targetRoute, feedRoute } from '../lib/dashView'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { Chip } from '../components/Chip'
import { postavkiStatusChip, procStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
```

- [ ] **Step 2: Add the `CompactTables` sub-component (above `export function Dashboard()`)**

```typescript
function CompactTables({
  data,
  onRow,
  onSection,
}: {
  data: DashboardTables
  onRow: (route: string) => void
  onSection: (route: string) => void
}) {
  const awaitingCols: DataTableColumn<AwaitingRow>[] = [
    {
      key: 'title',
      header: 'Наименование',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    { key: 'mtr', header: 'Тип МТР', render: (r) => r.mtr ?? '—' },
    { key: 'srok', header: 'Срок', render: (r) => dateRu(r.srok) },
    { key: 'position_count', header: 'Поз.', align: 'center', width: '10%' },
    { key: 'status', header: 'Статус', width: '18%' },
  ]

  const procurementCols: DataTableColumn<ProcurementRow>[] = [
    {
      key: 'title',
      header: 'Наименование',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    { key: 'num', header: '№ заявки', render: (r) => r.num ?? '—' },
    { key: 'supplier', header: 'Поставщик', render: (r) => r.supplier ?? '—' },
    { key: 'position_count', header: 'Поз.', align: 'center', width: '10%' },
    {
      key: 'status_zakup',
      header: 'Статус',
      width: '18%',
      render: (r) => <Chip {...procStatusChip(r.status_zakup)} mini />,
    },
  ]

  const supportCols: DataTableColumn<SupportRow>[] = [
    {
      key: 'title',
      header: 'Наименование',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    { key: 'num', header: '№ заявки', render: (r) => r.num ?? '—' },
    { key: 'supplier', header: 'Поставщик', render: (r) => r.supplier ?? '—' },
    {
      key: 'contract_sum',
      header: 'Сумма договора',
      align: 'right',
      render: (r) => <span className="dt">{money(r.contract_sum)}</span>,
    },
    {
      key: 'status_postavki',
      header: 'Статус поставки',
      width: '16%',
      render: (r) => <Chip {...postavkiStatusChip(r.status_postavki)} mini />,
    },
    {
      key: 'overdue_pct',
      header: 'Просроч.',
      align: 'center',
      width: '10%',
      render: (r) => {
        const v = Math.round(r.overdue_pct)
        const cls = v >= 50 ? 'b' : v > 0 ? 'w' : ''
        return <span className={`ovd ${cls}`}>{v}%</span>
      },
    },
    {
      key: 'progress',
      header: 'Прогресс',
      align: 'center',
      width: '14%',
      render: (r) => {
        const pct = r.total ? Math.round((r.delivered / r.total) * 100) : 0
        return (
          <div className="prog">
            <div className="bar">
              <i style={{ width: `${pct}%` }} />
            </div>
            <span className="pn">
              <b>{r.delivered}</b>/{r.total}
            </span>
          </div>
        )
      },
    },
  ]

  const block = (
    num: string,
    color: string,
    title: string,
    eng: string,
    total: number,
    route: string,
    inner: ReactNode,
  ) => (
    <div className="block" style={{ '--bc': `var(${color})` } as CSSProperties}>
      <div className="block-h">
        <span className="bnum">{num}</span>
        <div>
          <div className="btitle">{title}</div>
          <div className="beng">{eng}</div>
        </div>
        <span className="bcount">{total}</span>
        <span className="sp" />
        <button className="blink" onClick={() => onSection(route)}>
          Открыть раздел →
        </button>
      </div>
      <div className="tbl-scroll">{inner}</div>
    </div>
  )

  return (
    <>
      <div className="eyebrow" style={{ margin: '6px 0 10px' }}>
        Заявки по этапам
      </div>
      {block('1', 'wait', 'Ожидают закупки', 'Awaiting', data.awaiting.total, '/komplektaciya',
        <DataTable<AwaitingRow>
          className="fit"
          columns={awaitingCols}
          rows={data.awaiting.items}
          getRowId={(r) => r.id}
          onRowClick={(r) => onRow(`/komplektaciya/${r.id}`)}
          empty={<span className="empty-state">Нет заявок</span>}
        />,
      )}
      {block('2', 'proc', 'В закупке', 'In procurement', data.procurement.total, '/zakupka',
        <DataTable<ProcurementRow>
          className="fit"
          columns={procurementCols}
          rows={data.procurement.items}
          getRowId={(r) => r.id}
          onRowClick={(r) => onRow(`/zakupka/${r.id}`)}
          empty={<span className="empty-state">Нет процедур</span>}
        />,
      )}
      {block('3', 'supp', 'В сопровождении', 'In support', data.support.total, '/soprovozhdenie',
        <DataTable<SupportRow>
          className="fit"
          columns={supportCols}
          rows={data.support.items}
          getRowId={(r) => r.id}
          onRowClick={(r) => onRow(`/soprovozhdenie/${r.id}`)}
          empty={<span className="empty-state">Нет процедур</span>}
        />,
      )}
    </>
  )
}
```

- [ ] **Step 3: Render `CompactTables` in `Dashboard()`**

Replace the `{/* Компактные таблицы — Task 5 */}` placeholder with:

```typescript
      <CompactTables
        data={d.tables}
        onRow={(route) => navigate(route)}
        onSection={(route) => navigate(route)}
      />
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 5: Run the full FE suite**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: vitest green (incl. `dashView`), no new lint errors, build succeeds.

- [ ] **Step 6: Visual verify (⏸)**

On `/dashboard`: 3 `.block` compact tables (Ожидают закупки / В закупке / В сопровождении), each with a number badge, true total in `.bcount`, top-10 rows, «Открыть раздел →» → full page, row click → card. Support table shows sum/`Chip` status/`ovd` %/`prog` bar. Dispatch `ui-checker` for the full `#view-dash` (density/tokens, transitions, ru-RU formats, ≥1280px, clean console/network).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(dashboard): compact tables awaiting/procurement/support (Phase 8.2 T5)"
```

---

## ⏸ STOP — Phase 8.2 verification (before Phase 9)

- [ ] `cd frontend && npm test` → green (incl. `dashView`).
- [ ] `cd frontend && npx tsc -b` → no errors.
- [ ] `cd frontend && npm run lint` → no new lint errors.
- [ ] `cd frontend && npm run build` → succeeds.
- [ ] Full dashboard on dev (backend `:8000` + `npm run dev`):
  - `/` lands on `/dashboard`; 6 meters match a hand-recount per `32 §6`; seg-bars render.
  - Flow rail: 4 stages, click → page; counts match meters.
  - «Требует внимания»: red errors above amber warnings; «Открыть» → card; «и ещё N» when >20; identical under every role.
  - «Лента событий»: newest-first, actor + action + entity + relative time; parent/payment clickable.
  - Compact tables: top-10 + true totals; row → card; «Открыть раздел →» → page.
  - Numbers update within ~60 s (or on window focus).
- [ ] **🔎 ui-checker** on the whole «Дашборд» vs `Concept design/index.html` `#view-dash`: meter grid (6 → 3 → 2 cols on resize), flow arrows, two panels, 3 compact blocks, ru-RU money/date, desktop ≥1280/1440, no console errors / failed requests.
- [ ] **Wait for user confirmation before Phase 9.**

## Deferred (out of Phase 8)

- Global search → Фаза 10. Export (Excel/PDF/CSV) → Фаза 9. Dedicated audit «История» page → Фаза 10. 1С integration → `docs/34 §1`. Feed «rich» details (amounts/qty) — `audit_log` doesn't snapshot them.
