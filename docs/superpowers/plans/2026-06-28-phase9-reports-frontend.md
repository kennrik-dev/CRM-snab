# Phase 9 «Отчёты + экспорт» — Frontend 9.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `Otchety.tsx` page (params panel + KPIs + report tables + Excel/PDF/CSV export buttons) over the finished Phase 9.1 backend, gated to roles with `reports:view`, replacing the `/otchety` placeholder.

**Architecture:** One new page `pages/Otchety.tsx` (left `.rep-params` sticky panel + right `.rep-out` with `.rep-kpis` + `.rtbl` tables + `.exp` buttons) using one `useQuery(['reports', params])` for the snapshot and one `useQuery(['reports','filters'])` for dropdown options. One new `api/reports.ts` (typed `getReport`/`getFilters`/`downloadReport`). One new `lib/reportsView.ts` (pure cell-render descriptor + filename/period helpers, vitest-tested). Gating: `Tabs.tsx` hides the «Отчёты» tab and `Otchety.tsx` redirects to `/dashboard` when `!canView(perms,'reports')`. **No new CSS** (all `.rep-*`/`.rtbl`/`.daypill`/`.exp` classes exist) and **no new routes** (`/otchety` exists; swap placeholder → `<Otchety/>`).

**Tech Stack:** Vite + React 19 + TypeScript + React Router 7 + @tanstack/react-query 5, vitest (node env — pure-logic tests only).

**Design spec:** `docs/superpowers/specs/2026-06-28-phase9-reports-design.md` (§5 cell contract, §8 frontend, §9 filter options). **Depends on:** backend plan `2026-06-28-phase9-reports-backend.md` (Phase 9.1) being complete and merged/available.

## Global Constraints

- **API client:** every call via `apiFetch<T>(path, {method, body})` (`api/client.ts`, prepends `/api`, `credentials:'include'`, throws `{status, body}` on non-ok, handles 401). Query strings via `buildQuery(params)` (`api/support.ts`, skips undefined/null/`''`).
- **No jsdom/testing-library** — vitest tests cover **pure logic only** (`lib/reportsView.test.ts`). Components are verified via `tsc -b` + `npm run build` + 🔎 ui-checker (Playwright).
- **Money/date cells are pre-formatted by the backend** (snapshot cells are strings like «1 500 ₽», «12.04.26»); the FE renders them as-is, styling only by `kind`.
- **Reuse CSS** — `.rep-layout/.rep-params/.rep-group/.rg-l/.rep-opt(+.on)/.rep-sel/.rep-go/.rep-out/.rep-out-h/.exp/.rep-kpis/.rep-kpi/.l/.v/.rtbl/th/td.r/.mono/tfoot/.daypill(.warn/.bad)/.parent-tag/.cellsub/.dt.late/.tbl-scroll/.dsec-t/.empty-state/.wrap/.page-h/.sp`. Add **no** new CSS.
- **RBAC FE-gate = `canView(perms,'reports')`** (UX only; server enforces). Сотрудник отдела sees no tab and is redirected from `/otchety`.
- **Filter dropdowns** populated from `GET /reports` distinct `{mtr,supplier,author}`; first option «Все …» (value `''`).
- **Export** = `downloadReport(type, flt, format)`: `fetch('/api/reports/<type>/export?<flt>&format=', {credentials:'include'})` → blob → anchor click with filename from `Content-Disposition` (or `buildFilename`).
- After all tasks: `npm test` green, `tsc -b` 0 errors, `npm run lint` clean (Phase 9.2 files), `npm run build` OK, then 🔎 ui-checker, then **⏸ STOP** for user.

## File Structure

- **Create** `frontend/src/api/reports.ts` — types mirroring `schemas/reports.py` + `getReport/getFilters/downloadReport`. (No test — mirrors `api/payments.ts`.)
- **Create** `frontend/src/lib/reportsView.ts` — pure `describeCell/cellText/colorClass/buildFilename/periodOptionLabel`. (Has vitest test.)
- **Create** `frontend/src/lib/reportsView.test.ts` — pure-logic tests.
- **Create** `frontend/src/pages/Otchety.tsx` — the page (+ inline `ReportTable`/`CellView`).
- **Modify** `frontend/src/App.tsx` — swap `<PlaceholderPage title="Отчёты"/>` → `<Otchety/>`.
- **Modify** `frontend/src/components/Tabs.tsx` — hide the «Отчёты» tab when `!canView(perms,'reports')`.

Decomposition: Task 1 = api client; Task 2 = pure view helpers (TDD); Task 3 = the page + route swap; Task 4 = role gating; Task 5 = 🔎 ui-checker + full FE gate.

---

## Task 1: `api/reports.ts` — typed client

**Files:**
- Create: `frontend/src/api/reports.ts`

**Interfaces:**
- Consumes: `apiFetch` (`./client`), `buildQuery` (`./support`); backend `schemas/reports.py`.
- Produces: types `ReportType, ExportFormat, ReportPeriodKey, CellObj, Cell, Column, Section, Kpi, PeriodInfo, ReportSnapshot, Filters, ReportFilters`; functions `getReport(type, flt)`, `getFilters()`, `downloadReport(type, flt, format)`.

- [ ] **Step 1: Write `frontend/src/api/reports.ts` (complete)**

```typescript
import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало backend schemas/reports.py (Фаза 9.1). Слепок отчёта — generic-форма;
// money/date cells — предформатированные строки (BE).

export type ReportType = 'time' | 'sums' | 'late' | 'people'
export type ExportFormat = 'excel' | 'pdf' | 'csv'
export type ReportPeriodKey = 'month' | 'quarter' | 'year' | 'custom'

export type CellObj = {
  text?: string | null
  kind?: string | null      // claim|mono|text|stage|days|money|date|date-late|percent|note
  color?: string | null     // kind='stage': '--proc'
  level?: string | null     // kind='days': ''|'warn'|'bad'
  code?: string | null      // kind='claim': parent code
  title?: string | null     // kind='claim': title
}
export type Cell = string | CellObj

export type Column = { key: string; label: string; kind?: string | null; align?: string | null }
export type Section = {
  title?: string | null
  columns: Column[]
  rows: Cell[][]
  footer?: Cell[] | null
}
export type Kpi = { label: string; value: string; color?: string | null }
// BE serializes PeriodInfo.from_ with alias "from" → JSON key is "from".
export type PeriodInfo = { key: string; label: string; from?: string | null; to?: string | null }
export type ReportSnapshot = {
  type: string
  title: string
  period: PeriodInfo | null
  kpis: Kpi[]
  sections: Section[]
}
export type Filters = { mtr: string[]; supplier: string[]; author: string[] }
export type ReportFilters = {
  period?: ReportPeriodKey
  date_from?: string
  date_to?: string
  mtr?: string
  supplier?: string
  author?: string
}

export function getReport(type: ReportType, flt: ReportFilters): Promise<ReportSnapshot> {
  return apiFetch<ReportSnapshot>(`/reports/${type}${buildQuery(flt)}`)
}

export function getFilters(): Promise<Filters> {
  return apiFetch<Filters>('/reports')
}

// File download — bypasses apiFetch (which parses JSON); we need the binary blob.
export async function downloadReport(
  type: ReportType,
  flt: ReportFilters,
  format: ExportFormat,
): Promise<void> {
  const q = buildQuery({ ...flt, format })
  const res = await fetch(`/api/reports/${type}/export${q}`, { credentials: 'include' })
  if (!res.ok) {
    throw { status: res.status, body: await res.json().catch(() => null) }
  }
  const blob = await res.blob()
  const disp = res.headers.get('content-disposition') || ''
  const m = /filename="?([^"]+)"?/i.exec(disp)
  const filename =
    m?.[1] ||
    `otchety_${type}.${format === 'excel' ? 'xlsx' : format}`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: 0 errors (the file compiles; `apiFetch`/`buildQuery` resolve).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/reports.ts
git commit -m "feat(reports): typed api client — getReport/getFilters/downloadReport (Phase 9.2 T1)"
```

---

## Task 2: `lib/reportsView.ts` — pure cell/filename helpers (TDD)

**Files:**
- Create: `frontend/src/lib/reportsView.ts`
- Test: `frontend/src/lib/reportsView.test.ts`

**Interfaces:**
- Consumes: types from `api/reports`.
- Produces: `colorClass(token)`, `describeCell(cell) → {className, text, tag?}`, `cellText(cell)`, `buildFilename(type, format, dateIso)`, `periodOptionLabel(key)`.

- [ ] **Step 1: Write the failing tests `frontend/src/lib/reportsView.test.ts`**

```typescript
import { describe, it, expect } from 'vitest'
import {
  colorClass, describeCell, cellText, periodOptionLabel,
} from './reportsView'

describe('reportsView', () => {
  it('colorClass strips the -- prefix', () => {
    expect(colorClass('--proc')).toBe('proc')
    expect(colorClass('--supp')).toBe('supp')
    expect(colorClass(undefined)).toBe('')
    expect(colorClass(null)).toBe('')
  })

  it('describeCell: plain string passthrough', () => {
    expect(describeCell('ООО Ромашка')).toEqual({ className: '', text: 'ООО Ромашка' })
  })

  it('describeCell: claim → tag (code) + text (title)', () => {
    expect(describeCell({ kind: 'claim', code: 'Т-67', title: 'Трубы' }))
      .toEqual({ className: '', text: 'Трубы', tag: 'Т-67' })
  })

  it('describeCell: days → daypill + level class', () => {
    expect(describeCell({ kind: 'days', text: '12 дн.', level: 'warn' }))
      .toEqual({ className: 'daypill warn', text: '12 дн.' })
    expect(describeCell({ kind: 'days', text: '2 дн.', level: '' }))
      .toEqual({ className: 'daypill', text: '2 дн.' })
  })

  it('describeCell: stage → chip + colorClass', () => {
    expect(describeCell({ kind: 'stage', text: 'В закупке', color: '--proc' }))
      .toEqual({ className: 'chip proc', text: 'В закупке' })
  })

  it('describeCell: date-late / money / percent / note', () => {
    expect(describeCell({ kind: 'date-late', text: '01.04.26' }))
      .toEqual({ className: 'dt late', text: '01.04.26' })
    expect(describeCell({ kind: 'money', text: '1 500 ₽' }))
      .toEqual({ className: 'mono', text: '1 500 ₽' })
    expect(describeCell({ kind: 'percent', text: '40%' }))
      .toEqual({ className: 'mono', text: '40%' })
    expect(describeCell({ kind: 'note', text: 'нет' }))
      .toEqual({ className: 'cellsub', text: 'нет' })
  })

  it('cellText: claim concatenates code + title', () => {
    expect(cellText({ kind: 'claim', code: 'Т-67', title: 'Трубы' })).toBe('Т-67 Трубы')
    expect(cellText('plain')).toBe('plain')
  })

  it('periodOptionLabel', () => {
    expect(periodOptionLabel('month')).toBe('Текущий месяц')
    expect(periodOptionLabel('quarter')).toBe('Квартал')
    expect(periodOptionLabel('year')).toBe('С начала года')
    expect(periodOptionLabel('custom')).toBe('Произвольный')
    expect(periodOptionLabel('')).toBe('Весь период')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/reportsView.test.ts`
Expected: FAIL — module `./reportsView` not found.

- [ ] **Step 3: Write `frontend/src/lib/reportsView.ts`**

```typescript
import type { Cell } from '../api/reports'

export function colorClass(token: string | null | undefined): string {
  if (!token) return ''
  return token.replace(/^--/, '')
}

export type RenderedCell = { className: string; text: string; tag?: string }

export function describeCell(cell: Cell): RenderedCell {
  if (typeof cell === 'string') return { className: '', text: cell }
  const text = cell.text ?? ''
  switch (cell.kind) {
    case 'claim':
      return { className: '', text: cell.title ?? '', tag: cell.code ?? '—' }
    case 'stage':
      return { className: `chip ${colorClass(cell.color)}`.trim(), text }
    case 'days':
      return { className: `daypill ${cell.level || ''}`.trim(), text }
    case 'date-late':
      return { className: 'dt late', text }
    case 'money':
    case 'percent':
      return { className: 'mono', text }
    case 'note':
      return { className: 'cellsub', text }
    default:
      return { className: '', text }
  }
}

export function cellText(cell: Cell): string {
  if (typeof cell === 'string') return cell
  if (cell.kind === 'claim') return `${cell.code ?? '—'} ${cell.title ?? ''}`.trim()
  return cell.text ?? ''
}

export function periodOptionLabel(
  key: '' | 'month' | 'quarter' | 'year' | 'custom',
): string {
  switch (key) {
    case 'month': return 'Текущий месяц'
    case 'quarter': return 'Квартал'
    case 'year': return 'С начала года'
    case 'custom': return 'Произвольный'
    default: return 'Весь период'
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/reportsView.test.ts`
Expected: all pass (`reportsView` suite green).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/reportsView.ts frontend/src/lib/reportsView.test.ts
git commit -m "feat(reports): pure view helpers — describeCell/buildFilename/period (Phase 9.2 T2)"
```

---

## Task 3: `pages/Otchety.tsx` + route swap

**Files:**
- Create: `frontend/src/pages/Otchety.tsx`
- Modify: `frontend/src/App.tsx` (import + replace placeholder route)

**Interfaces:**
- Consumes: `getReport/getFilters/downloadReport` + types (`api/reports`); `describeCell` (`lib/reportsView`); `canView` (`lib/permissions`); `useAuth` (`auth/AuthContext`); CSS classes from `zakupki-crm.css`.
- Produces: `<Otchety/>` mounted at `/otchety`; renders params panel (type/period/filters), KPI bar, `.rtbl` tables per section, export buttons (Excel/PDF/CSV); empty state «По выбранным параметрам нет данных»; redirects to `/dashboard` when `!canView`.

- [ ] **Step 1: Write `frontend/src/pages/Otchety.tsx` (complete)**

```tsx
import { useState, type CSSProperties } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  getReport, getFilters, downloadReport,
  type ReportType, type ReportFilters, type ExportFormat, type Cell,
  type ReportSnapshot,
} from '../api/reports'
import { describeCell, periodOptionLabel } from '../lib/reportsView'
import { canView } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: 'time', label: 'Время на этапе / зависания' },
  { value: 'sums', label: 'Суммы по этапам и поставщикам' },
  { value: 'late', label: 'Просрочки: поставки и оплаты' },
  { value: 'people', label: 'Сводка по составителям/отделам' },
]
const PERIOD_KEYS = ['', 'month', 'quarter', 'year', 'custom'] as const
const FORMATS: { value: ExportFormat; label: string }[] = [
  { value: 'excel', label: 'Excel' },
  { value: 'pdf', label: 'PDF' },
  { value: 'csv', label: 'CSV' },
]

function CellView({ cell }: { cell: Cell }) {
  const d = describeCell(cell)
  if (d.tag !== undefined) {
    return (
      <>
        <span className="parent-tag">{d.tag}</span>
        {d.text}
      </>
    )
  }
  return <span className={d.className}>{d.text}</span>
}

function ReportTable({ section }: { section: ReportSnapshot['sections'][number] }) {
  return (
    <div>
      {section.title && (
        <div className="dsec-t" style={{ padding: '12px 16px 6px' }}>{section.title}</div>
      )}
      <div className="tbl-scroll">
        <table className="rtbl">
          <thead>
            <tr>
              {section.columns.map((c) => (
                <th key={c.key} className={c.align === 'right' ? 'r' : ''}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} className={section.columns[j]?.align === 'right' ? 'r' : ''}>
                    <CellView cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {section.footer && (
            <tfoot>
              <tr>
                {section.footer.map((cell, j) => (
                  <td key={j} className={section.columns[j]?.align === 'right' ? 'r' : ''}>
                    <CellView cell={cell} />
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

export function Otchety() {
  const { permissions } = useAuth()
  const [params, setParams] = useState<ReportFilters & { type: ReportType }>({ type: 'time' })

  const report = useQuery({
    queryKey: ['reports', params],
    queryFn: () => getReport(params.type, params),
  })
  const filters = useQuery({ queryKey: ['reports', 'filters'], queryFn: getFilters })

  if (!canView(permissions, 'reports')) return <Navigate to="/dashboard" replace />

  const set = (patch: Partial<typeof params>) => setParams((p) => ({ ...p, ...patch }))
  const snap = report.data
  const hasRows = (snap?.sections ?? []).some((s) => s.rows.length > 0 && !(s.rows.length === 1 && s.rows[0][0] && typeof s.rows[0][0] === 'object' && (s.rows[0][0] as { kind?: string }).kind === 'note'))

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>Отчёты</h1>
        <span className="desc">конструктор выгрузок для руководства</span>
        <span className="sp" />
      </div>

      <div className="rep-layout">
        <div className="rep-params">
          <h3>Параметры</h3>

          <div className="rep-group">
            <div className="rg-l">Тип отчёта</div>
            {REPORT_TYPES.map((t) => (
              <div
                key={t.value}
                className={`rep-opt${params.type === t.value ? ' on' : ''}`}
                onClick={() => set({ type: t.value })}
              >
                <i />
                {t.label}
              </div>
            ))}
          </div>

          <div className="rep-group">
            <div className="rg-l">Период</div>
            <select
              className="rep-sel"
              value={params.period ?? ''}
              onChange={(e) =>
                set({ period: (e.target.value || undefined) as ReportFilters['period'] })
              }
            >
              {PERIOD_KEYS.map((k) => (
                <option key={k} value={k}>{periodOptionLabel(k)}</option>
              ))}
            </select>
            {params.period === 'custom' && (
              <>
                <input
                  type="date" className="rep-sel"
                  value={params.date_from ?? ''}
                  onChange={(e) => set({ date_from: e.target.value || undefined })}
                />
                <input
                  type="date" className="rep-sel"
                  value={params.date_to ?? ''}
                  onChange={(e) => set({ date_to: e.target.value || undefined })}
                />
              </>
            )}
          </div>

          <div className="rep-group">
            <div className="rg-l">Фильтры</div>
            <select className="rep-sel" value={params.mtr ?? ''}
              onChange={(e) => set({ mtr: e.target.value || undefined })}>
              <option value="">Все типы МТР</option>
              {(filters.data?.mtr ?? []).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
            <select className="rep-sel" value={params.supplier ?? ''}
              onChange={(e) => set({ supplier: e.target.value || undefined })}>
              <option value="">Все поставщики</option>
              {(filters.data?.supplier ?? []).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
            <select className="rep-sel" value={params.author ?? ''}
              onChange={(e) => set({ author: e.target.value || undefined })}>
              <option value="">Все составители</option>
              {(filters.data?.author ?? []).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>

          <button className="rep-go" onClick={() => report.refetch()}>
            {report.isFetching ? 'Формирование…' : 'Сформировать'}
          </button>
        </div>

        <div className="rep-out">
          {report.isLoading ? (
            <div className="empty-state">Загрузка…</div>
          ) : report.isError ? (
            <div className="empty-state">
              Ошибка:{' '}
              {String(
                (report.error as { body?: { detail?: string } })?.body?.detail ?? report.error,
              )}
            </div>
          ) : !snap ? null : !hasRows ? (
            <div className="empty-state">По выбранным параметрам нет данных</div>
          ) : (
            <>
              <div className="rep-out-h">
                <h2>{snap.title}</h2>
                <span className="sp" />
                <div className="exp">
                  {FORMATS.map((f) => (
                    <button key={f.value} onClick={() => downloadReport(params.type, params, f.value)}>
                      ↧ {f.label}
                    </button>
                  ))}
                </div>
              </div>
              {snap.kpis.length > 0 && (
                <div className="rep-kpis">
                  {snap.kpis.map((k, i) => (
                    <div className="rep-kpi" key={i}>
                      <div className="l">{k.label}</div>
                      <div
                        className="v"
                        style={
                          k.color ? ({ color: `var(${k.color})` } as CSSProperties) : undefined
                        }
                      >
                        {k.value}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {snap.sections.map((s, i) => (
                <ReportTable key={i} section={s} />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
```

> **`hasRows` note:** a section whose only row is the `{kind:'note', text:'нет'}` placeholder (emitted by `report_late` for an empty Поставки/Оплаты section) must NOT count as data — the check above excludes it. If every section is empty/«нет», the page shows «По выбранным параметрам нет данных».

- [ ] **Step 2: Wire the route in `frontend/src/App.tsx`**

Add the import (alphabetical, after `Oplaty`):

```typescript
import { Otchety } from './pages/Otchety'
```

Replace the placeholder route:

```typescript
        <Route path="/otchety" element={<PlaceholderPage title="Отчёты" />} />
```

with:

```typescript
        <Route path="/otchety" element={<Otchety />} />
```

(`PlaceholderPage` stays — it may still be referenced nowhere now; leave the function as-is, do not delete unless `tsc` flags it unused. If `tsc -b`/lint flags it unused, remove it.)

- [ ] **Step 3: Typecheck + build**

Run: `cd frontend && npx tsc -b && npm run build`
Expected: 0 type errors; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Otchety.tsx frontend/src/App.tsx
git commit -m "feat(reports): Otchety page — params + KPIs + tables + export (Phase 9.2 T3)"
```

---

## Task 4: role gating — hide tab + redirect

**Files:**
- Modify: `frontend/src/components/Tabs.tsx`
- (Otchety redirect already in place from Task 3.)

**Interfaces:**
- Consumes: `useAuth` (`auth/AuthContext`), `canView` (`lib/permissions`).
- Produces: the «Отчёты» tab hidden when `!canView(perms,'reports')`.

- [ ] **Step 1: Gate the tab in `frontend/src/components/Tabs.tsx`**

Add imports at the top:

```typescript
import { useAuth } from '../auth/AuthContext'
import { canView } from '../lib/permissions'
```

Inside the `Tabs` component, before `return (`, read permissions and filter the tab list:

```typescript
  const { permissions } = useAuth()
  const tabs = TABS.filter(
    (t) => t.to !== '/otchety' || canView(permissions, 'reports'),
  )
```

Replace `TABS.map((t) => {` in the JSX with `tabs.map((t) => {`.

- [ ] **Step 2: Typecheck + lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: 0 errors; Phase 9.2 files lint-clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Tabs.tsx
git commit -m "feat(reports): hide «Отчёты» tab for roles without reports:view (Phase 9.2 T4)"
```

---

## Task 5: 🔎 ui-checker + full FE gate

**Files:** none (verification only).

- [ ] **Step 1: Full FE gate**

Run: `cd frontend && npm test && npx tsc -b && npm run lint && npm run build`
Expected: vitest green (incl. new `reportsView` suite), `tsc -b` 0 errors, lint clean, build OK.

- [ ] **Step 2: Smoke-check against running dev servers**

Ensure backend (`:8000`) + frontend (`:5173`) are running with seeded data and ≥1 procedure/delivery/УПД. Log in as admin (`admin@crm.local`).
- `/otchety` renders: left params panel (4 type options, period select, 3 filter selects populated), right output.
- Switch each of the 4 types → KPIs + table(s) render with correct columns; `late` empty sections show «нет».
- Pick period «Текущий месяц» → rows narrow to in-month; «Произвольный» → 2 date inputs appear.
- Click Excel / PDF / CSV → each downloads a non-empty file; open CSV in Excel (Cyrillic OK), open PDF (Cyrillic OK).
- Filter by supplier → rows narrow.

- [ ] **Step 3: 🔎 Dispatch `ui-checker`**

Dispatch the `ui-checker` agent with the Phase 9.2 scenario:
- «Отчёты» page: `.rep-layout` 280px/1fr grid, sticky `.rep-params`, `.rep-opt` type switcher (active = `.on`), `.rep-sel` selects, `.rep-go` button; `.rep-out` with `.rep-out-h` + `.exp` buttons, `.rep-kpis` (where present), `.rtbl` tables (`.r` right-align, `tfoot` totals, `.daypill` levels, `.chip` stages, `.parent-tag` claims, `.cellsub` «нет»). 
- Role gating: under a department employee (non-curator) the «Отчёты» tab is absent and `/otchety` redirects to `/dashboard`; under Куратор/Руководитель/Админ the tab + page work.
- Export: Excel/PDF/CSV download; CSV opens with correct Cyrillic + `;` separator.
- Desktop ≥1280px (and 1440px). Console + network clean (`GET /reports`, `GET /reports/<type>`, `GET /reports/<type>/export` → 200; no 401/403/422 except intentional employee-403).
- Canon: `Concept design/index.html` §REPORTS + `zakupki-crm.js:runReport`.
- Report format: PASS/FAIL + discrepancies by severity. (ui-checker is diagnostic only — it does not edit code; fix any FAIL in a follow-up commit, then re-run.)

- [ ] **Step 4: Commit any polish from ui-checker findings** (if any), then:

## ⏸ STOP — Phase 9 verification (end of Phase 9)

- [ ] Backend 9.1 + Frontend 9.2 both green: `cd backend && "$PY" -m pytest -q`; `cd frontend && npm test && npx tsc -b && npm run lint && npm run build`.
- [ ] 🔎 ui-checker PASS on «Отчёты».
- [ ] Human: as Руководитель/Админ/Куратор form all 4 reports, export all 3 formats; as a department employee confirm the tab is hidden and `/otchety` redirects.
- [ ] **Wait for user confirmation — Phase 9 complete; ready to merge `feat/phase-9` → `main` (FF) per project convention.**

Phase 10 (search/history/comments/nonfunctional/regression) is the next and final phase per the master plan.
