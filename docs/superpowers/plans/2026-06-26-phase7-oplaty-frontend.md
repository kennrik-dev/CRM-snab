# Phase 7 «Оплаты» — Frontend 7.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the «Оплаты» FE — summary hero + distribution bar, УПД registry with search/sort/hide-paid, «+ Добавить УПД» modal, payment card with editable fields + «Провести оплату», and the tab counter — over the already-shipped Phase 7.1 `/payments` backend.

**Architecture:** Mirror the established Phase-6.3 patterns: a new `api/payments.ts` (twin of `api/support.ts`); two pure helpers (`payStatusChip`, `buildPayBar`) with vitest; a new `pages/Oplaty.tsx` (structure copy of `pages/Soprovozhdenie.tsx`); a new `cards/PaymentCard.tsx` (draft/diff-save/refresh-await-before-reset copy of `cards/SupportCard.tsx`); plus `App.tsx` route wiring and a `Tabs.tsx` counter. RBAC gate is `canEdit(perms,'soprovozhdenie')` (NOT `oplaty` — design R2). **No CSS is added** — every class used (`.payhero/.pcard/.pbar/.sp-*/.utbl/.updn/.pchip/.pcd/.pcd-h/.pcd-meta/.pcd-body/.amt-big`) already exists in `frontend/src/styles/zakupki-crm.css`.

**Tech Stack:** React 19, Vite, TypeScript (strict), @tanstack/react-query v5, react-router-dom v6, Vitest. Backend: the Phase 7.1 `/payments` router (already on `main`/`feat/phase-7`).

**Design spec:** `docs/superpowers/specs/2026-06-26-phase7-oplaty-design.md` §4 (authoritative). Backend plan: `docs/superpowers/plans/2026-06-26-phase7-oplaty-backend.md` (DONE). Canonical visuals: `Concept design/index.html` (`#view-pay`, `#view-paycard`) + `Concept design/zakupki-crm.js` (`rPay`, `payFin`, `rPayCard`). Page/card text specs: `docs/13-page-oplaty.md`, `docs/17-card-platezh.md`.

**Scope locked with user (2026-06-26):** LEAN — the УПД positions editor is **deferred** (manual-УПД amount is hand-entered per `docs/13 §8`; positions drive no sum; BE already supports `positions` so a later micro-phase needs no backend change). The card shows positions **read-only**.

## Global Constraints

- **Money = INTEGER kopecks** end-to-end; **dates = ISO `YYYY-MM-DD` strings**. Render via `money()`/`dateRu()` from `lib/format.ts`; editable money fields bridge rubles↔kopecks via `rublesToKopecks()`/`kopecksToRublesInput()` from `lib/money.ts` (same pattern as `SupportCard.contract_sum`).
- **API:** every call goes through `apiFetch` in `api/client.ts` (adds `/api` prefix, `credentials:'include'`, 401→`auth:logout` event, throws `{status,body}`). Mirror `api/support.ts` exactly (same `buildQuery`, same shape).
- **RBAC FE-gate (R2):** `canEdit(permissions, 'soprovozhdenie')` gates the «+ Добавить УПД» button, the card «Сохранить»/«Провести оплату» buttons, and editable inputs. Do **not** use `'oplaty'` — a Сопровождение employee does not own the `oplaty` block, so `canEdit(perms,'oplaty')` would wrongly hide actions the backend permits.
- **React Query keys:** list `['payments',{search,hide_paid,sort,page}]`; summary `['payments','summary']`; tab counter `['payments',{tabCounter:true}]`; card detail `['payment', paymentId]` (singular, like `['procedure',id]`). After any mutation: `qc.invalidateQueries({queryKey:['payments']})` (refreshes list+summary+counter) **and** `await qc.refetchQueries({queryKey:['payment',paymentId]})` before resetting the draft (await-refetch-before-reset pitfall — see `SupportCard.refresh`).
- **No CSS changes.** If a class looks missing, re-read `styles/zakupki-crm.css:234-264` — it is there.
- **TDD where there is logic:** pure helpers (`payStatusChip`, `buildPayBar`) get vitest (red→green→commit). Components are verified by `npx tsc -b` (type-check) + the `ui-checker` Playwright agent at ⏸ stops (this matches the Phase 4 / 6.3 FE rhythm: pure fns unit-tested, components visually checked).
- **Surgical changes:** duplicate the small `useDebounced` hook inside `Oplaty.tsx` (do **not** refactor `Soprovozhdenie.tsx` to share it — that working file is not touched). Match existing style/idiom.
- **Commit prefix:** `feat(payments):` (or `test(payments):` for the pure-helper task). One commit per task.
- **Verify commands** (run from `frontend/`): type-check `npx tsc -b`; tests `npm test` (vitest run); lint `npm run lint`; full build `npm run build` (= `tsc -b && vite build`). Visual checks need `npm run dev` **and** the backend on `:8000` with some data.
- **Don't break the dev environment:** keep `crm.db`, uvicorn (`:8000`), and vite healthy.

## File Structure

- **Create** `frontend/src/api/payments.ts` — types + 6 endpoint wrappers (twin of `api/support.ts`).
- **Create** `frontend/src/lib/payView.ts` — pure `buildPayBar(bar)` (distribution-bar segments). Tested.
- **Create** `frontend/src/lib/payView.test.ts` — vitest for `buildPayBar`.
- **Modify** `frontend/src/lib/statusColors.ts` — add pure `payStatusChip(status, isOverdue)`.
- **Modify** `frontend/src/lib/statusColors.test.ts` — add vitest for `payStatusChip`.
- **Create** `frontend/src/pages/Oplaty.tsx` — summary hero + bar + FilterBar + registry `DataTable` + «+ Добавить УПД» modal (sub-component `AddUpdModal`).
- **Create** `frontend/src/cards/PaymentCard.tsx` — payment card (draft/diff-save + pay).
- **Modify** `frontend/src/App.tsx` — `/oplaty` → `<Oplaty/>`; add `/oplaty/:id` → `<PaymentCard/>`.
- **Modify** `frontend/src/components/Tabs.tsx` — wire the «Оплаты» await counter.

Decomposition: pure helpers first (T1, testable in isolation); then the api module they + the UI lean on (T2); then the read+create registry page (T3, T4); then the card (T5); then the tab counter (T6). Each task is one reviewer gate.

---

## Task 1: Pure helpers — `payStatusChip` + `buildPayBar` (TDD)

**Files:**
- Modify: `frontend/src/lib/statusColors.ts`
- Modify: `frontend/src/lib/statusColors.test.ts`
- Create: `frontend/src/lib/payView.ts`
- Create: `frontend/src/lib/payView.test.ts`

**Interfaces:**
- Consumes: `ChipKind` from `components/Chip.tsx` (already imported in `statusColors.ts`).
- Produces: `payStatusChip(payStatus, isOverdue?) -> {kind: ChipKind; label: string}` and `buildPayBar(bar) -> PayBarSegment[]` where `PayBarSegment = {cls: string; value: number; widthPct: number; labelPct: number}`. Later tasks render the status cell via `<Chip {...payStatusChip(r.pay_status, r.is_overdue)} mini />` and the bar via the 4 segments.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/lib/statusColors.test.ts` (add `payStatusChip` to the existing import on line 2):

```typescript
import { procStatusChip, sdelkiStatusChip, postavkiStatusChip, payStatusChip } from './statusColors'
```

Append this `describe` at the end of the file:

```typescript
describe('payStatusChip', () => {
  it('paid → ok «Оплачено»', () => {
    expect(payStatusChip('paid')).toEqual({ kind: 'ok', label: 'Оплачено' })
    expect(payStatusChip('paid', true)).toEqual({ kind: 'ok', label: 'Оплачено' }) // paid is never overdue
  })
  it('await / not overdue → proc «Ожидает оплаты»', () => {
    expect(payStatusChip('await', false)).toEqual({ kind: 'proc', label: 'Ожидает оплаты' })
    expect(payStatusChip('await')).toEqual({ kind: 'proc', label: 'Ожидает оплаты' })
  })
  it('await / overdue → late «Просрочена»', () => {
    expect(payStatusChip('await', true)).toEqual({ kind: 'late', label: 'Просрочена' })
  })
  it('null/undefined/"" → wait «—»', () => {
    expect(payStatusChip(null)).toEqual({ kind: 'wait', label: '—' })
    expect(payStatusChip(undefined)).toEqual({ kind: 'wait', label: '—' })
    expect(payStatusChip('')).toEqual({ kind: 'wait', label: '—' })
  })
})
```

Create `frontend/src/lib/payView.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { buildPayBar } from './payView'

const BAR = { paid: 100000, await_: 200000, delivered_no_upd: 300000, contracted_no_delivery: 400000 }
// total = 1 000 000

describe('buildPayBar', () => {
  it('returns 4 segments in canon order with fractional widths that sum to 100', () => {
    const s = buildPayBar(BAR)
    expect(s.map((x) => x.cls)).toEqual(['sp-paid', 'sp-out', 'sp-del', 'sp-con'])
    expect(s.map((x) => x.value)).toEqual([100000, 200000, 300000, 400000])
    // widthPct is exact (fractional) so the bar always fills 100%.
    expect(s.reduce((a, x) => a + x.widthPct, 0)).toBeCloseTo(100, 5)
    expect(s[0].widthPct).toBeCloseTo(10, 5)
  })
  it('labelPct is the rounded percent for the segment text', () => {
    const s = buildPayBar(BAR)
    expect(s.map((x) => x.labelPct)).toEqual([10, 20, 30, 40])
  })
  it('a zero-valued segment still appears with 0 width/label', () => {
    const s = buildPayBar({ paid: 0, await_: 500000, delivered_no_upd: 0, contracted_no_delivery: 500000 })
    expect(s[0]).toMatchObject({ cls: 'sp-paid', value: 0, widthPct: 0, labelPct: 0 })
    expect(s[1].widthPct).toBeCloseTo(50, 5)
  })
  it('total 0 → all segments 0 (no divide-by-zero)', () => {
    const s = buildPayBar({ paid: 0, await_: 0, delivered_no_upd: 0, contracted_no_delivery: 0 })
    expect(s.every((x) => x.widthPct === 0 && x.labelPct === 0)).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- payView.test.ts statusColors.test.ts`
Expected: FAIL — `payStatusChip` is not exported; `buildPayBar` module not found.

- [ ] **Step 3: Implement `payStatusChip`**

Append to `frontend/src/lib/statusColors.ts`:

```typescript
/**
 * pay_status (+ overdue flag) → { chip kind, label }. Pure; unit-tested.
 * Maps the «Оплаты» pay_status to the same color tokens the canon `.pchip`
 * uses (proc/late/ok), rendered via the generic <Chip>.
 * - 'paid'            → ok   «Оплачено» (paid is never overdue).
 * - 'await' + overdue → late «Просрочена».
 * - 'await'           → proc «Ожидает оплаты».
 * - null/""           → wait «—».
 */
export function payStatusChip(
  payStatus: string | null | undefined,
  isOverdue: boolean = false,
): { kind: ChipKind; label: string } {
  if (payStatus === 'paid') return { kind: 'ok', label: 'Оплачено' }
  if (payStatus === 'await') {
    return isOverdue ? { kind: 'late', label: 'Просрочена' } : { kind: 'proc', label: 'Ожидает оплаты' }
  }
  if (!payStatus) return { kind: 'wait', label: '—' }
  return { kind: 'wait', label: payStatus }
}
```

- [ ] **Step 4: Implement `buildPayBar`**

Create `frontend/src/lib/payView.ts`:

```typescript
/**
 * Pure view helpers for the «Оплаты» page (mirror of lib/supportView.ts).
 *
 * buildPayBar: turns the 4 summary.bar amounts into renderable segments in
 * canon order (paid → await → delivered-no-upd → contracted-no-delivery).
 * `widthPct` is the EXACT fractional percent (so the `.pbar` always sums to
 * 100% width); `labelPct` is the rounded percent shown inside the segment.
 * total = 0 → all segments 0 (the bar renders empty, no divide-by-zero).
 */
export type PayBarSegment = {
  cls: string
  value: number
  widthPct: number
  labelPct: number
}

export type PayBar = {
  paid: number
  await_: number
  delivered_no_upd: number
  contracted_no_delivery: number
}

export function buildPayBar(bar: PayBar): PayBarSegment[] {
  const total = bar.paid + bar.await_ + bar.delivered_no_upd + bar.contracted_no_delivery
  const seg = (cls: string, value: number): PayBarSegment => {
    const widthPct = total > 0 ? (value / total) * 100 : 0
    return { cls, value, widthPct, labelPct: Math.round(widthPct) }
  }
  return [
    seg('sp-paid', bar.paid),
    seg('sp-out', bar.await_),
    seg('sp-del', bar.delivered_no_upd),
    seg('sp-con', bar.contracted_no_delivery),
  ]
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- payView.test.ts statusColors.test.ts`
Expected: PASS (all new + existing assertions green).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/statusColors.ts frontend/src/lib/statusColors.test.ts frontend/src/lib/payView.ts frontend/src/lib/payView.test.ts
git commit -m "test(payments): payStatusChip + buildPayBar pure helpers (Phase 7.2 T1)"
```

---

## Task 2: `api/payments.ts` (types + endpoints)

**Files:**
- Create: `frontend/src/api/payments.ts`

**Interfaces:**
- Consumes: `apiFetch` from `api/client.ts`; `buildQuery` is re-used — import it from `api/support.ts` (it is already exported there and unit-tested; do not duplicate).
- Produces: types `PaymentSort`, `UpdPositionOut`, `PaymentListItem`, `PaginatedPayments`, `PaymentDeliveryOut`, `PaymentDetail`, `PaymentCreate`, `PaymentPatch`, `PaymentsSummary`, `SummaryMeters`, `SummaryBar`; functions `listPayments`, `getPayment`, `createPayment`, `patchPayment`, `payPayment`, `getPaymentsSummary`. These match the Phase 7.1 backend schemas verbatim (`backend/app/schemas/payments.py`).

> No vitest here — the module is types + thin `apiFetch` wrappers with no new runtime logic (`buildQuery` is already covered by `api/support.test.ts`). The gate is `tsc -b` green + the contract matching the BE schemas below.

- [ ] **Step 1: Write `frontend/src/api/payments.ts`**

```typescript
import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало backend schemas/payments.py (Фаза 7.1). Деньги — int копейки,
// даты — ISO 'YYYY-MM-DD' строки (Optional).

// Whitelist sort-ключей бэкенда GET /payments (_SORT_KEYS в payments.py):
export type PaymentSort =
  | 'created_at'
  | 'upd'
  | 'request'
  | 'supplier'
  | 'contract'
  | 'zrds'
  | 'status'
  | 'srok'
  | 'amount'

export type UpdPositionOut = {
  id: number
  n: number | null
  name: string | null
  unit: string | null
  qty: number | null
  price: number | null
}

export type PaymentListItem = {
  id: number
  upd: string
  origin: string
  request_display: string | null
  supplier: string | null
  contract: string | null
  zrds: string | null
  delivery_n: number | null
  pay_status: string
  is_overdue: boolean
  srok: string | null
  pay_date: string | null
  amount: number | null
  created_at: string
}

export type PaginatedPayments = { items: PaymentListItem[]; total: number }

export type PaymentDeliveryOut = {
  n: number
  procedure_id: number
  parent_code: string | null
}

export type PaymentDetail = {
  id: number
  upd: string
  origin: string
  delivery_id: number | null
  request_label: string | null
  supplier: string | null
  contract: string | null
  zrds: string | null
  srok: string | null
  amount: number | null
  pay_status: string
  pay_date: string | null
  created_at: string
  positions: UpdPositionOut[]
  delivery: PaymentDeliveryOut | null
  is_overdue: boolean
}

export type PaymentCreate = {
  upd: string
  request_label?: string
  supplier?: string
  srok?: string
  amount?: number
  zrds?: string
  // LEAN (2026-06-26): positions editor deferred — manual amount is hand-entered
  // (docs/13 §8), so the FE never sends `positions`. BE still accepts it.
}

export type PaymentPatch = {
  srok?: string | null
  zrds?: string | null
  contract?: string | null
  supplier?: string | null
  amount?: number | null
}

export type SummaryMeters = { paid: number; await_: number; overdue: number; in_work: number }
export type SummaryBar = {
  paid: number
  await_: number
  delivered_no_upd: number
  contracted_no_delivery: number
}
export type PaymentsSummary = { meters: SummaryMeters; bar: SummaryBar }

// ---- Endpoints ------------------------------------------------------------

export function listPayments(params: {
  search?: string
  hide_paid?: boolean
  sort?: PaymentSort
  page?: number
  page_size?: number
} = {}): Promise<PaginatedPayments> {
  return apiFetch<PaginatedPayments>(`/payments${buildQuery(params)}`)
}

export function getPaymentsSummary(): Promise<PaymentsSummary> {
  return apiFetch<PaymentsSummary>('/payments/summary')
}

export function getPayment(id: number): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>(`/payments/${id}`)
}

export function createPayment(payload: PaymentCreate): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>('/payments', { method: 'POST', body: payload })
}

export function patchPayment(id: number, payload: PaymentPatch): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>(`/payments/${id}`, { method: 'PATCH', body: payload })
}

export function payPayment(id: number): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>(`/payments/${id}/pay`, { method: 'POST' })
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS (no errors). If `buildQuery` import from `./support` errors, confirm `support.ts` exports it (it does, line 8).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/payments.ts
git commit -m "feat(payments): api/payments.ts types + endpoints (Phase 7.2 T2)"
```

---

## Task 3: `pages/Oplaty.tsx` (read-only: summary + bar + filter + registry) + route

**Files:**
- Create: `frontend/src/pages/Oplaty.tsx`
- Modify: `frontend/src/App.tsx` (import + route)

**Interfaces:**
- Consumes: `listPayments`, `getPaymentsSummary`, types from `api/payments.ts`; `buildPayBar` from `lib/payView.ts`; `payStatusChip` from `lib/statusColors.ts`; `DataTable`/`DataTableColumn`, `FilterBar`, `EmptyState`, `Chip`; `money`/`dateRu` from `lib/format.ts`.
- Produces: exported `Oplaty` component mounted at `/oplaty` (Task 4 appends the «+ Добавить УПД» modal; Task 6 the tab counter).

- [ ] **Step 1: Write `frontend/src/pages/Oplaty.tsx` (read-only version)**

```typescript
import { useMemo, useState, useEffect, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  listPayments,
  getPaymentsSummary,
  type PaymentListItem,
  type PaymentSort,
} from '../api/payments'
import { buildPayBar } from '../lib/payView'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { Chip } from '../components/Chip'
import { payStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'

const SORT_OPTIONS: { value: PaymentSort; label: string }[] = [
  { value: 'created_at', label: 'По дате создания' },
  { value: 'upd', label: 'По № УПД' },
  { value: 'request', label: 'По заявке' },
  { value: 'supplier', label: 'По поставщику' },
  { value: 'contract', label: 'По договору' },
  { value: 'zrds', label: 'По ЗРДС' },
  { value: 'status', label: 'По статусу оплаты' },
  { value: 'srok', label: 'По сроку' },
  { value: 'amount', label: 'По сумме' },
]

// Search debounce (same pattern as Soprovozhdenie — duplicated intentionally,
// see plan Global Constraints).
function useDebounced<T>(value: T, delay: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), delay)
    return () => window.clearTimeout(t)
  }, [value, delay])
  return v
}

// ---- Summary hero + distribution bar --------------------------------------

function PaySummary() {
  const q = useQuery({
    queryKey: ['payments', 'summary'],
    queryFn: getPaymentsSummary,
  })
  if (q.isError) return null
  if (!q.data) {
    // Loading skeleton: 4 empty cards so the layout doesn't jump.
    return (
      <div className="payhero">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="pcard" style={{ '--c': 'var(--line)' } as CSSProperties}>
            <div className="pl">…</div>
            <div className="pv">…</div>
          </div>
        ))
      </div>
    )
  }
  const m = q.data.meters
  const segs = buildPayBar(q.data.bar).filter((s) => s.value > 0)
  const card = (label: string, val: number, token: string, sub?: string) => (
    <div className="pcard" style={{ '--c': `var(--${token})` } as CSSProperties}>
      <div className="pl">{label}</div>
      <div className="pv">{money(val)}</div>
      {sub && <div className="pvsub">{sub}</div>}
    </div>
  )
  return (
    <>
      <div className="payhero">
        {card('Сумма в работе', m.in_work, 'ink', 'оплачено + к оплате')}
        {card('Оплачено', m.paid, 'ok')}
        {card('К оплате', m.await_, 'proc')}
        {card('Просрочено', m.overdue, 'late')}
      </div>
      <div className="pbar">
        {segs.map((s) => (
          <span key={s.cls} className={s.cls} style={{ width: `${s.widthPct}%` }}>
            {s.labelPct}%
          </span>
        ))}
      </div>
    </>
  )
}

// ---- Page -----------------------------------------------------------------

export function Oplaty() {
  const navigate = useNavigate()

  const [searchInput, setSearchInput] = useState('')
  const [nonSearch, setNonSearch] = useState<{ hide_paid: boolean; sort: PaymentSort }>({
    hide_paid: false,
    sort: 'created_at',
  })
  const debouncedSearch = useDebounced(searchInput, 300)

  const list = useQuery({
    queryKey: ['payments', { search: debouncedSearch, ...nonSearch }],
    queryFn: () =>
      listPayments({
        search: debouncedSearch || undefined,
        hide_paid: nonSearch.hide_paid || undefined,
        sort: nonSearch.sort,
        page: 1,
        page_size: 100,
      }),
  })

  const items = useMemo(() => list.data?.items ?? [], [list.data])
  const total = list.data?.total ?? 0

  const columns = useMemo<DataTableColumn<PaymentListItem>[]>(
    () => [
      {
        key: 'upd',
        header: 'УПД',
        width: '11%',
        render: (r) => <span className="updn">{r.upd}</span>,
      },
      {
        key: 'request_display',
        header: 'Заявка',
        width: '12%',
        render: (r) => r.request_display ?? '—',
      },
      {
        key: 'supplier',
        header: 'Поставщик',
        width: '15%',
        render: (r) => r.supplier ?? '—',
      },
      {
        key: 'contract',
        header: 'Договор',
        width: '12%',
        render: (r) => r.contract ?? '—',
      },
      {
        key: 'zrds',
        header: 'ЗРДС',
        width: '10%',
        render: (r) => r.zrds ?? '—',
      },
      {
        key: 'delivery_n',
        header: 'Поставка',
        width: '7%',
        align: 'center',
        render: (r) => r.delivery_n ?? '—',
      },
      {
        key: 'pay_status',
        header: 'Статус',
        width: '12%',
        render: (r) => <Chip {...payStatusChip(r.pay_status, r.is_overdue)} mini />,
      },
      {
        key: 'srok',
        header: 'Срок',
        width: '8%',
        render: (r) => dateRu(r.srok),
      },
      {
        key: 'amount',
        header: 'Сумма',
        width: '13%',
        align: 'right',
        render: (r) => <span className="dt">{money(r.amount)}</span>,
      },
    ],
    [],
  )

  const hasFilterApplied = debouncedSearch.trim() !== '' || nonSearch.hide_paid

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>Оплаты</h1>
        <span className="desc">реестр платежей по УПД</span>
        <span className="sp" />
      </div>

      <PaySummary />

      <FilterBar>
        <input
          type="text"
          className="rep-sel"
          style={{ minWidth: 220 }}
          placeholder="Поиск: № УПД, заявка, поставщик, договор, ЗРДС…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          className="rep-sel"
          value={nonSearch.sort}
          onChange={(e) => setNonSearch((s) => ({ ...s, sort: e.target.value as PaymentSort }))}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={nonSearch.hide_paid}
            onChange={(e) => setNonSearch((s) => ({ ...s, hide_paid: e.target.checked }))}
          />
          Скрыть оплаченные
        </label>
      </FilterBar>

      <div className="block" style={{ '--bc': 'var(--pay)' } as CSSProperties}>
        <div className="block-h">
          <span className="bnum">О</span>
          <div>
            <div className="btitle">Реестр платежей</div>
            <div className="beng">Payments</div>
          </div>
          <span className="bcount">{total}</span>
          <span className="sp" />
        </div>
        <div className="tbl-scroll">
          {list.isLoading ? (
            <div className="empty-state">Загрузка…</div>
          ) : list.isError ? (
            <EmptyState
              title="Ошибка загрузки"
              hint={String(
                (list.error as { body?: { detail?: string } })?.body?.detail ?? list.error,
              )}
            />
          ) : (
            <DataTable<PaymentListItem>
              className="fit"
              columns={columns}
              rows={items}
              getRowId={(r) => r.id}
              onRowClick={(row) => navigate(`/oplaty/${row.id}`)}
              empty={
                <EmptyState
                  title={hasFilterApplied ? 'Ничего не найдено' : 'Нет платежей'}
                  hint={
                    hasFilterApplied
                      ? undefined
                      : 'УПД появляются здесь автоматически из поставок или кнопкой «+ Добавить УПД».'
                  }
                />
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Wire the route in `frontend/src/App.tsx`**

Change the import block (add `Oplaty` to the page imports, keep order):

```typescript
import { Komplektaciya } from './pages/Komplektaciya'
import { Zakupka } from './pages/Zakupka'
import { Soprovozhdenie } from './pages/Soprovozhdenie'
import { Oplaty } from './pages/Oplaty'
```

Replace the `/oplaty` placeholder route (line 40) with the real page:

```typescript
        <Route path="/oplaty" element={<Oplaty />} />
```

(The `/oplaty/:id` card route is added in Task 5.)

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 4: Visual verify (⏸ — requires backend on :8000 + dev data)**

With `cd frontend && npm run dev` and the backend running, sign in as admin and open `/oplaty`. Expect: 4 summary cards (`.payhero`), a distribution bar (`.pbar`), a registry table with `.fit` columns; row click navigates to `/oplaty/:id` (card lands in Task 5 — a blank/404 page is OK for now).
Dispatch the `ui-checker` agent to confirm layout vs `Concept design/index.html` `#view-pay` and the absence of console errors / failed requests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Oplaty.tsx frontend/src/App.tsx
git commit -m "feat(payments): Oplaty page — summary + bar + registry (Phase 7.2 T3)"
```

---

## Task 4: «+ Добавить УПД» modal on `pages/Oplaty.tsx`

**Files:**
- Modify: `frontend/src/pages/Oplaty.tsx` (add `useMutation`, `useQueryClient`, `useAuth`, `canEdit`, `rublesToKopecks`, `Modal`, `createPayment`; add `AddUpdModal` sub-component + wire it into `Oplaty`)

**Interfaces:**
- Consumes: `createPayment` + `PaymentCreate` from `api/payments.ts`; `Modal` from `components/Modal.tsx`; `canEdit` + `useAuth`; `rublesToKopecks` from `lib/money.ts`.
- Produces: a «+ Добавить УПД» button (gated by `canEdit(perms,'soprovozhdenie')`) in the `FilterBar` actions that opens a modal; on submit → `POST /payments` → invalidate `['payments']` → close.

- [ ] **Step 1: Extend imports in `Oplaty.tsx`**

Replace the existing import block top of `Oplaty.tsx` (the `react`/`react-router`/`react-query` lines) with:

```typescript
import { useMemo, useState, useEffect, type CSSProperties, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listPayments,
  getPaymentsSummary,
  createPayment,
  type PaymentListItem,
  type PaymentSort,
  type PaymentCreate,
} from '../api/payments'
import { buildPayBar } from '../lib/payView'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { Chip } from '../components/Chip'
import { Modal } from '../components/Modal'
import { payStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { rublesToKopecks } from '../lib/money'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'
```

- [ ] **Step 2: Append the `AddUpdModal` sub-component at the bottom of `Oplaty.tsx`**

```typescript
// ---- Add-УПД modal (manual) -----------------------------------------------

const addFieldStyle: CSSProperties = {
  padding: '6px 8px',
  border: '1px solid var(--line)',
  borderRadius: 4,
  fontSize: 13,
  background: 'var(--surface)',
  width: '100%',
}
const addLabelStyle: CSSProperties = {
  fontSize: 10,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'var(--faint)',
  fontWeight: 600,
  marginBottom: 3,
  display: 'block',
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <span style={addLabelStyle}>{label}</span>
      {children}
    </div>
  )
}

// Mount-controlled (like SplitDialog in ProcedureCard): the parent renders
// `{addOpen && <AddUpdModal .../>}` so each open gets a fresh form state.
function AddUpdModal({
  onClose,
  onCreate,
  pending,
}: {
  onClose: () => void
  onCreate: (payload: PaymentCreate) => void
  pending: boolean
}) {
  const [f, setF] = useState({
    upd: '',
    request_label: '',
    supplier: '',
    srok: '',
    amount: '',
    zrds: '',
  })
  const valid = f.upd.trim() !== ''

  function submit() {
    if (!valid || pending) return
    onCreate({
      upd: f.upd.trim(),
      request_label: f.request_label.trim() || undefined,
      supplier: f.supplier.trim() || undefined,
      srok: f.srok || undefined,
      amount: rublesToKopecks(f.amount) ?? undefined,
      zrds: f.zrds.trim() || undefined,
    })
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Добавить УПД"
      width={560}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={pending}>
            Отмена
          </button>
          <button className="btn primary" onClick={submit} disabled={!valid || pending}>
            {pending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label="№ УПД *">
          <input
            style={addFieldStyle}
            value={f.upd}
            onChange={(e) => setF((s) => ({ ...s, upd: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Заявка">
          <input
            style={addFieldStyle}
            placeholder="Т-67 + №"
            value={f.request_label}
            onChange={(e) => setF((s) => ({ ...s, request_label: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Поставщик">
          <input
            style={addFieldStyle}
            value={f.supplier}
            onChange={(e) => setF((s) => ({ ...s, supplier: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Срок">
          <input
            type="date"
            style={addFieldStyle}
            value={f.srok}
            onChange={(e) => setF((s) => ({ ...s, srok: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Сумма с НДС (₽)">
          <input
            style={addFieldStyle}
            inputMode="decimal"
            placeholder="0,00"
            value={f.amount}
            onChange={(e) => setF((s) => ({ ...s, amount: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="№ ЗРДС">
          <input
            style={addFieldStyle}
            value={f.zrds}
            onChange={(e) => setF((s) => ({ ...s, zrds: e.target.value }))}
            disabled={pending}
          />
        </Field>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 3: Wire the modal into the `Oplaty` component**

Inside `export function Oplaty()`, add (right after `const navigate = useNavigate()`):

```typescript
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')
  const [addOpen, setAddOpen] = useState(false)

  const createMut = useMutation({
    mutationFn: (payload: PaymentCreate) => createPayment(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['payments'] })
      setAddOpen(false)
    },
  })
```

Add the «+ Добавить УПД» button by passing an `actions` prop to `FilterBar` (the component already forwards `actions`). Change the `<FilterBar>` opening tag to:

```typescript
      <FilterBar
        actions={
          canEditThis ? (
            <button className="btn primary" onClick={() => setAddOpen(true)}>
              + Добавить УПД
            </button>
          ) : undefined
        }
      >
```

Finally, render the modal just before the closing `</div>` of the page (after the `.block`):

```typescript
      {addOpen && (
        <AddUpdModal
          onClose={() => setAddOpen(false)}
          onCreate={(payload) => createMut.mutate(payload)}
          pending={createMut.isPending}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 5: Visual verify (⏸)**

On `/oplaty` as a Сопровождение user / admin: the «+ Добавить УПД» button is visible; it opens the modal; filling № УПД + fields and saving creates a manual УПД that appears at the top of the registry with status «Ожидает оплаты», origin manual (no Поставка number), and the summary updates. Dispatch `ui-checker`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Oplaty.tsx
git commit -m "feat(payments): + Добавить УПД modal (Phase 7.2 T4)"
```

---

## Task 5: `cards/PaymentCard.tsx` + `/oplaty/:id` route

**Files:**
- Create: `frontend/src/cards/PaymentCard.tsx`
- Modify: `frontend/src/App.tsx` (import `PaymentCard` + add `/oplaty/:id` route)

**Interfaces:**
- Consumes: `getPayment`, `patchPayment`, `payPayment`, `PaymentDetail`, `PaymentPatch` from `api/payments.ts`; `payStatusChip`; `Chip`, `EmptyState`; `money`/`dateRu`; `kopecksToRublesInput`/`rublesToKopecks`; `canEdit` + `useAuth`.
- Produces: exported `PaymentCard` mounted at `/oplaty/:id`. Draft/diff-save mirrors `SupportCard` (R2 gate: `canEdit(perms,'soprovozhdenie')`).

> **LEAN scope note (flagged):** the card shows positions **read-only** (no inline editor) and **omits the ТТН/М-15/УПД/Серт doc toggles** — those flags live on `Delivery`, are not part of `PaymentDetail`, and are managed on the support card (design R9 made them read-only anyway). The linked delivery cross-reference (`PaymentDetail.delivery`) IS shown. Editable scalar fields = exactly the `PaymentPatch` set: `supplier, contract, zrds, srok, amount`. `request_label` is not PATCHable → read-only.

- [ ] **Step 1: Write `frontend/src/cards/PaymentCard.tsx`**

```typescript
import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getPayment,
  patchPayment,
  payPayment,
  type PaymentDetail,
  type PaymentPatch,
} from '../api/payments'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import { payStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { kopecksToRublesInput, rublesToKopecks } from '../lib/money'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

type PayDraft = {
  supplier: string
  contract: string
  zrds: string
  srok: string
  amount: string // rubles input string
}

function draftFromPayment(p: PaymentDetail): PayDraft {
  return {
    supplier: p.supplier ?? '',
    contract: p.contract ?? '',
    zrds: p.zrds ?? '',
    srok: p.srok ?? '',
    amount: kopecksToRublesInput(p.amount),
  }
}

/** Diff draft vs server → only changed PaymentPatch fields (empty string → null). */
function buildPatch(d: PayDraft, p: PaymentDetail): PaymentPatch | null {
  const patch: PaymentPatch = {}
  const cur = draftFromPayment(p)
  const setStr = (field: keyof PaymentPatch, dk: keyof PayDraft) => {
    if (d[dk] !== cur[dk]) {
      ;(patch as Record<string, unknown>)[field as string] = d[dk] === '' ? null : d[dk]
    }
  }
  setStr('supplier', 'supplier')
  setStr('contract', 'contract')
  setStr('zrds', 'zrds')
  setStr('srok', 'srok')
  // money round-trip (как contract_sum в SupportCard)
  if (rublesToKopecks(d.amount) !== p.amount) {
    patch.amount = rublesToKopecks(d.amount)
  }
  return Object.keys(patch).length ? patch : null
}

function lastErrorMessage(err: unknown): string {
  const e = err as { body?: { detail?: string } } | null
  return e?.body?.detail ?? 'Не удалось сохранить'
}

const fieldStyle: CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: 6,
  padding: '6px 8px',
  fontFamily: 'inherit',
  fontSize: 13,
  width: '100%',
}

export function PaymentCard() {
  const { id } = useParams()
  const paymentId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')

  const payQ = useQuery({
    queryKey: ['payment', paymentId],
    queryFn: () => getPayment(paymentId),
    enabled: Number.isFinite(paymentId),
  })
  const p = payQ.data

  const [draft, setDraft] = useState<PayDraft | null>(null)
  const [savedTick, setSavedTick] = useState(0)
  const [actionErr, setActionErr] = useState<string | null>(null)

  // reset draft on payment change / load
  useEffect(() => {
    setDraft(null)
    setActionErr(null)
  }, [paymentId])

  const refresh = useCallback(async () => {
    // Await the card refetch BEFORE resetting the local draft (await-refetch-
    // before-reset pitfall — see SupportCard.refresh). Then invalidate the
    // list/summary/counter so the registry + hero reflect the change.
    await qc.refetchQueries({ queryKey: ['payment', paymentId] })
    qc.invalidateQueries({ queryKey: ['payments'] })
    setDraft(null)
  }, [qc, paymentId])

  const saveMut = useMutation({
    mutationFn: (payload: PaymentPatch) => patchPayment(paymentId, payload),
    onSuccess: async () => {
      await refresh()
      setSavedTick((t) => t + 1)
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const payMut = useMutation({
    mutationFn: () => payPayment(paymentId),
    onSuccess: async () => {
      await refresh()
      setSavedTick((t) => t + 1)
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  useEffect(() => {
    if (!savedTick) return
    const idt = setTimeout(() => setSavedTick(0), 2500)
    return () => clearTimeout(idt)
  }, [savedTick])

  if (payQ.isLoading) return <div className="wrap"><p className="desc">Загрузка…</p></div>
  if (payQ.isError || !p)
    return (
      <div className="wrap">
        <EmptyState title="Платёж не найден" hint="Возможно, он удалён или нет прав." />
      </div>
    )

  const d = draft ?? draftFromPayment(p)
  const patch = draft ? buildPatch(draft, p) : null
  const status = payStatusChip(p.pay_status, p.is_overdue)
  const isPaid = p.pay_status === 'paid'
  const requestDisplay = p.request_label ?? p.delivery?.parent_code ?? null

  function setField<K extends keyof PayDraft>(k: K, v: PayDraft[K]) {
    setDraft((prev) => ({ ...(prev ?? draftFromPayment(p!)), [k]: v }))
  }

  // meta cells: editable ones render an <input>, the rest a read-only .v
  const editableCell = (label: string, key: keyof PayDraft, value: string, type?: string) => (
    <div className="m">
      <div className="l">{label}</div>
      {canEditThis ? (
        <input
          style={fieldStyle}
          type={type}
          inputMode={key === 'amount' ? 'decimal' : undefined}
          value={value}
          onChange={(e) => setField(key, e.target.value)}
        />
      ) : (
        <div className="v">{value || '—'}</div>
      )}
    </div>
  )
  const readOnlyCell = (label: string, value: string) => (
    <div className="m">
      <div className="l">{label}</div>
      <div className="v">{value || '—'}</div>
    </div>
  )

  return (
    <div className="wrap">
      <button className="back" onClick={() => navigate('/oplaty')}>
        ‹ Оплаты
      </button>

      <div className="pcd">
        <div className="pcd-h">
          <div className="top">
            <div style={{ flex: 1, minWidth: 260 }}>
              <h1>{p.upd}</h1>
              <div className="mt">
                <b>Заявка:</b> {requestDisplay ?? '—'} · <b>Поставка:</b>{' '}
                {p.delivery ? `№${p.delivery.n}` : '— (ручная УПД)'}
              </div>
            </div>
            <span className="sp" />
            <span className="amt-big">{money(p.amount)}</span>
          </div>
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
            <Chip kind={status.kind} label={status.label} />
            {p.pay_date && (
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                оплачено {dateRu(p.pay_date)}
              </span>
            )}
          </div>
          {actionErr && (
            <div style={{ color: 'var(--late)', fontSize: 12, marginTop: 8 }}>{actionErr}</div>
          )}
        </div>

        <div className="pcd-meta">
          {readOnlyCell('Заявка', requestDisplay ?? '')}
          {editableCell('Поставщик', 'supplier', d.supplier)}
          {editableCell('Договор', 'contract', d.contract)}
          {editableCell('№ ЗРДС', 'zrds', d.zrds)}
          {editableCell('Срок', 'srok', d.srok, 'date')}
          {editableCell('Сумма с НДС (₽)', 'amount', d.amount)}
          {readOnlyCell('Дата оплаты', p.pay_date ? dateRu(p.pay_date) : '')}
          {readOnlyCell(
            'Поставка',
            p.delivery ? `№${p.delivery.n} · ${p.delivery.parent_code ?? '—'}` : '',
          )}
        </div>

        <div className="pcd-body">
          <div
            className="actbar"
            style={{ background: 'transparent', border: 'none', padding: '0 0 14px' }}
          >
            {canEditThis && (
              <button
                className="btn primary"
                disabled={!patch || saveMut.isPending}
                onClick={() => patch && saveMut.mutate(patch)}
              >
                {saveMut.isPending ? 'Сохранение…' : 'Сохранить'}
              </button>
            )}
            {savedTick > 0 && <span style={{ color: 'var(--ok)', fontSize: 12 }}>✓ Сохранено</span>}
            <span className="sp" />
            {canEditThis && (
              <button
                className="btn primary"
                disabled={isPaid || payMut.isPending}
                onClick={() => {
                  if (isPaid || payMut.isPending) return
                  if (window.confirm('Провести оплату? Дата оплаты будет зафиксирована.')) {
                    payMut.mutate()
                  }
                }}
              >
                {payMut.isPending ? 'Оплата…' : 'Провести оплату'}
              </button>
            )}
          </div>

          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--faint)',
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            Позиции в УПД ({p.positions.length})
          </div>
          <div className="tbl-scroll">
            <table className="postbl">
              <thead>
                <tr>
                  <th>№</th>
                  <th>Наименование</th>
                  <th>Ед.</th>
                  <th>Кол-во</th>
                  <th>Цена с НДС</th>
                  <th>Сумма</th>
                </tr>
              </thead>
              <tbody>
                {p.positions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      Нет позиций
                    </td>
                  </tr>
                ) : (
                  p.positions.map((pos) => (
                    <tr key={pos.id}>
                      <td>{pos.n ?? '—'}</td>
                      <td>{pos.name ?? '—'}</td>
                      <td>{pos.unit ?? '—'}</td>
                      <td>{pos.qty ?? '—'}</td>
                      <td>{money(pos.price)}</td>
                      <td>
                        {money(
                          pos.price != null && pos.qty != null
                            ? Math.round(pos.qty * pos.price)
                            : null,
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Wire the card route in `frontend/src/App.tsx`**

Add the import (next to the other card imports):

```typescript
import { PaymentCard } from './cards/PaymentCard'
```

Add the route immediately after the `/oplaty` route (before `/otchety`):

```typescript
        <Route path="/oplaty/:id" element={<PaymentCard />} />
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 4: Visual verify (⏸)**

Open a payment from the registry (both a delivery-УПД and a manual one). Expect: header with № УПД + status chip + big amount; meta grid with editable supplier/contract/zrds/srok/amount and read-only Заявка/Дата оплаты/Поставка; read-only positions table; «Сохранить» (enabled only when a field changed) and «Провести оплату» (disabled when paid). Conducting payment flips the chip to «Оплачено», sets Дата оплаты, disables the button, and updates the registry + summary on back-navigation. A Сопровождение employee sees the buttons; a Комплектация employee does not (R2). Dispatch `ui-checker` (canon `#view-paycard`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/cards/PaymentCard.tsx frontend/src/App.tsx
git commit -m "feat(payments): PaymentCard + /oplaty/:id route (Phase 7.2 T5)"
```

---

## Task 6: «Оплаты» tab counter

**Files:**
- Modify: `frontend/src/components/Tabs.tsx`

**Interfaces:**
- Consumes: `listPayments` from `api/payments.ts` (created in Task 2).
- Produces: the «Оплаты» tab badge shows the count of **unpaid** УПД (`pay_status='await'`) — obtained cheaply as `listPayments({hide_paid:true, page_size:1}).total` (design R11).

- [ ] **Step 1: Edit `frontend/src/components/Tabs.tsx`**

Add the import (with the other `api` imports near the top):

```typescript
import { listPayments } from '../api/payments'
```

Add the counter key (next to `SOPP_COUNTER_KEY`):

```typescript
const OPLAT_COUNTER_KEY = ['payments', { tabCounter: true }] as const
```

Add the query inside `Tabs()` (next to the `sopp` query) and its derived total:

```typescript
  const oplat = useQuery({
    queryKey: OPLAT_COUNTER_KEY,
    queryFn: () => listPayments({ hide_paid: true, page_size: 1 }),
  })
  const oplatTotal = oplat.data?.total
```

Update the `count` resolver chain in the `TABS.map` callback so the `/oplaty` branch returns the unpaid count. Replace the existing `const count = ...` ternary with:

```typescript
        const count =
          t.to === '/komplektaciya'
            ? (komplTotal ?? '—')
            : t.to === '/zakupka'
              ? (zakupTotal ?? '—')
              : t.to === '/soprovozhdenie'
                ? (soppTotal ?? '—')
                : t.to === '/oplaty'
                  ? (oplatTotal ?? '—')
                  : t.showCounter
                    ? '—'
                    : null
```

Also update the stale comment block above the counter keys (it says the oplat tab still renders `—`) — replace it with:

```typescript
// Counter queries fetch page_size=1 so the backend only sends the `total`
// count and no payload rows. The «Оплаты» counter = unpaid УПД
// (hide_paid=true → total is the await count).
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 3: Visual verify (⏸)**

The «Оплаты» tab shows a number = count of unpaid УПД. Conducting a payment on the card decrements it (the `['payments']` invalidation from Task 5 refreshes the counter). Dispatch `ui-checker`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Tabs.tsx
git commit -m "feat(payments): Оплаты tab counter = unpaid УПД (Phase 7.2 T6)"
```

---

## ⏸ STOP — Phase 7.2 verification (before Phase 8)

- [ ] `cd frontend && npm test` → all green (incl. new `payStatusChip` / `buildPayBar`).
- [ ] `cd frontend && npx tsc -b` → no errors.
- [ ] `cd frontend && npm run lint` → no new lint errors.
- [ ] `cd frontend && npm run build` → succeeds.
- [ ] Full flow on dev (backend `:8000` + `npm run dev`, admin / Сопровождение user):
  - `/oplaty` renders summary hero (4 cards) + distribution bar + registry; search / sort / «скрыть оплаченные» work.
  - «+ Добавить УПД» creates a manual УПД (status «Ожидает оплаты», no Поставка) that appears in the registry and bumps the tab counter.
  - Row → payment card: editable fields save (draft/diff, «✓ Сохранено»); «Провести оплату» → «Оплачено» + Дата оплаты, button disables, 409 on a double is prevented by the disabled state.
  - Tab counter reflects unpaid count and updates after paying.
- [ ] **🔎 ui-checker** on the whole «Оплаты» flow vs `Concept design/index.html` (`#view-pay`, `#view-paycard`): hero/bar segments + %, registry `.fit` columns + status chips + «—» for empty manual fields, modal form, card meta grid + read-only positions + «Провести оплату», ru-RU money/date formats, desktop ≥1280px, no console errors / failed requests.
- [ ] **Wait for user confirmation before Phase 8.**

## Deferred (out of LEAN 7.2, by user decision 2026-06-26)

- **УПД positions editor** (modal optional + card inline, full-replace via `PATCH positions`) — manual amount is hand-entered (`docs/13 §8`), positions drive no sum; BE already supports `positions`, so a later micro-phase needs no backend change.
- **Doc toggles (ТТН/М-15/УПД/Серт) on the payment card** — flags live on `Delivery`, not in `PaymentDetail`; managed on the support card (R9 read-only anyway). Shown linked-delivery cross-reference instead.
- № УПД in global search → Фаза 10. Export button + Excel/PDF/CSV → Фаза 9. Audit «История» on the card → Фаза 10. 1С integration → `docs/34 §1`.
