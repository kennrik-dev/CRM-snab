# Фаза 6.3 (frontend) — Страница «В сопровождении» + карточка Б2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. Реализуй строго по TDD для чистой логики (красный → зелёный → коммит); React-компоненты — implement → `tsc` → `ui-checker` (Playwright) на STOP-воротах. НЕ додумывай поля/имена — всё дословно из этого плана, `docs/12-page-v-soprovozhdenii.md`, `docs/16-card-zayavka.md` §4 и бэкенда Фазы 6.2. Главный агент верифицирует сам (`npx tsc --noEmit`, `npm test`, git log).

**Goal:** Frontend Фазы 6.3 — страница «В сопровождении» (`pages/Soprovozhdenie.tsx`, список процедур `block=soprovozhdenie` с in-row правкой Б2-полей и производными колонками) + **отдельная** карточка Б2 (`cards/SupportCard.tsx`: договор/сумма, статусы, Срок ДД/План/Факт, поставки, документы, № УПД) + API-слой `api/support.ts`. Бэкенд 6.2 уже реализован и зелёный.

**Architecture:** Фронтенд повторяет паттерны `Zakupka.tsx` (список) и `ProcedureCard.tsx` (карточка: `getProcedure` под `['procedure', id]`, `refresh()` await-refetch-then-reset, sister-switcher, saveAll diff-patch). **Карточка Б2 — отдельный компонент `SupportCard`** на маршруте `/soprovozhdenie/:id` (решение пользователя: изоляция, нулевой риск для рабочего Б1 `ProcedureCard`). API-слой — hook-free функции поверх `apiFetch` (как `api/procedures.ts`); react-query hooks живут в странице/карточке. Чистая логика (цвета статусов, пороги просрочки/прогресса, Σ позиций, маршрутизация сестёр, buildQuery) — в `lib/` с vitest-тестами; presentational-компоненты эмитят **уже существующие** CSS-классы (`.ovd`/`.docsq`/`.prog`/`.doctag`/`.pchip`) — новых стилей нет.

**Tech Stack:** React 19, TypeScript ~6, @tanstack/react-query v5, react-router-dom v7, Vite 8, vitest 4 (`environment: 'node'`, **только pure-function тесты — нет jsdom/@testing-library**), Playwright через агента `ui-checker` для UI-верификации. Деньги — INTEGER копейки (`money()`, `kopecksToRublesInput`/`rublesToKopecks`). Даты — ISO `YYYY-MM-DD` (`dateRu()` → ДД.ММ.ГГ).

## Global Constraints (дословно из `docs/` + конвенций проекта)
- Деньги — `INTEGER` копейки; `contract_sum`/`price` — копейки; отображение через `money()` (1 234 567 ₽), правка через `kopecksToRublesInput`/`rublesToKopecks`.
- Даты — ISO `YYYY-MM-DD` строки; `<input type='date'>`; отображение `dateRu()`.
- Список: пагинация `?page=&page_size=` (фронт тянет `page_size: 100`), ответ `{items, total}`; **активные по умолчанию**, `include_archived=1` — переключатель «Показать завершённые/отменённые».
- Роли: просмотр открыт всем («единое окно»); **правка** гейтится `canEdit(permissions, 'soprovozhdenie')` (`'soprovozhdenie'` уже в `Block` union, `lib/permissions.ts:1`). Редиректа/блокировки маршрута нет — read-only пользователи видят chips/текст вместо контролов.
- Query-ключи: список `['support', {search, include_archived, sort}]`; детальная карточка переиспользует `['procedure', id]` (тот же `getProcedure`); tab-counter `['support', {tabCounter:true}]`. После мутаций: список → `invalidateQueries(['support'])`; карточка → `await refetchQueries(['procedure', id])` → `invalidateQueries(['support'])` + `['request', parent_id]` → сброс драфтров (паттерн `refresh()`, **обязательно await перед reset** — pitfall #2 из MEMORY).
- In-row правка на странице: `status_sdelki`, `status_postavki`, `plan_date`, `fakt_date` (спека 12 §3); `srok_dd` и `contract*` — только в карточке. `status_sdelki` — из dict `status_sdelki` (3 значения); `status_postavki` — **хардкод enum** (6 значений, не dict).
- Бэкенд-контракт (уже реализован в 6.2): `GET /support`, `PATCH /procedures/{id}` (block-scoped Б2), `POST /procedures/{id}/deliveries`, `DELETE /deliveries/{id}`, `PATCH /deliveries/{id}`, `POST /deliveries/{id}/upd`.

## Зафиксированные решения (design, утверждено пользователем + спеками)
1. **Отдельная `SupportCard`** на `/soprovozhdenie/:id`; `ProcedureCard` (Б1) нетронут. Сёстры роутятся per-block через `sisterRoute(block, id)` (сестра в `soprovozhdenie` → `/soprovozhdenie/:id`, иначе `/zakupka/:id`); `block` есть в `ProcedureOut` (`api/requests.ts:42`).
2. **Позиции в Б2 — read-only** (спека 16 §4 не упоминает их редактирование); их только распределяют по поставкам. «Ожидают отгрузки» = позиции с `delivery_id === null`.
3. **In-row правка** = `status_sdelki`/`status_postavki`/`plan_date`/`fakt_date`; остальное (договор, сумма, `srok_dd`, поставки, документы, № УПД) — в карточке.
4. **`status_postavki` — хардкод enum** (6 значений); **`status_sdelki` — dict** (`listDict('status_sdelki')`).
5. **Просрочка** бакеты по `overdue_pct`: `≥50` → красный (`.ovd.b`); `>0` → оранжевый (`.ovd.w`); `0` → зелёный (`.ovd`).
6. **`StatusSelect` обобщается** опциональным пропом `color?: (v) => {kind, label}` (дефолт `procStatusChip`) — surgical, Б1 не ломается.
7. **Цвета статусов** (предложение, пользователь может поправить на review): `status_sdelki` — Подписано→ok, Подготовка ДД→teal, Согласование→wait, null→wait(«Не задано»), иное→proc; `status_postavki` — Поставлено→ok, Частично поставлено→pay, В поставке→supp, В производстве→teal, Новая→wait, Отменена→late, иное→proc.
8. **№ УПД → Оплаты** — серверный side-effect (бэкенд 6.2f upsert `upd_payment`); фронт только зовёт `upsertUpd` и показывает вернувшийся `pay_status`. Страница «Оплаты» — Фаза 7 (placeholder), сейчас не трогаем.
9. **Документы** в строке списка — агрегат «есть во **всех** поставках» (`docs_aggregate`, бэкенд); в карточке — per-delivery toggle (`.doctag`/`.doctag.no`, int 0/1).
10. **Тесты**: pure-логика — vitest (красный→зелёный); React — `tsc --noEmit` + агент `ui-checker` (Playwright) на STOP-воротах. Новый test-harness (jsdom) НЕ вводим (surgical, не ломаем dev-окружение).

## File Structure
- **Create:** `frontend/src/api/support.ts` (типы + эндпоинты), `frontend/src/lib/supportView.ts` (pure helpers + STATUS_POSTAVKI?), `frontend/src/lib/supportView.test.ts`, `frontend/src/components/support/OverduePct.tsx`, `…/Progress.tsx`, `…/DocsSquares.tsx`, `…/DocToggle.tsx`, `…/PayChip.tsx`, `frontend/src/components/support/DeliverySection.tsx`, `frontend/src/pages/Soprovozhdenie.tsx`, `frontend/src/cards/SupportCard.tsx`.
- **Modify:** `frontend/src/api/procedures.ts` (widen `ProcedureDetail`/`ProcedurePosition`/`ProcedurePatch`), `frontend/src/lib/statusColors.ts` (+ `sdelkiStatusChip`/`postavkiStatusChip`) + `statusColors.test.ts`, `frontend/src/components/StatusSelect.tsx` (+ optional `color` prop), `frontend/src/components/Tabs.tsx` (counter `/soprovozhdenie`), `frontend/src/App.tsx` (routes).

---

## Task 6.3.0 — Prep: baseline зелёный, на ветке feat/phase-6, бэкенд крутится

**Не TDD-задача** (env/git prep). Главный агент напрямую.

- [ ] **Шаг 1:** на ветке `feat/phase-6`, рабочий дерева чист (кроме скриншотов).
```bash
cd "H:/Projects AI/CRM Ultima"
git branch --show-current          # feat/phase-6
git log --oneline -3               # видны коммиты 6.2f … 6.1
```
- [ ] **Шаг 2: baseline frontend** — `tsc` и vitest зелёные ДО изменений.
```bash
cd frontend && npx tsc --noEmit    # 0 errors
cd frontend && npm test            # all PASS (фиксируем число тестов — после 6.3 должно вырасти)
```
- [ ] **Шаг 3 (smoke):** бэкенд + dev-сервер поднимаются (для ui-checker).
```bash
# backend (отдельный терминал): uvicorn app.main:app --reload  (порт 8000, /api)
# frontend: cd frontend && npm run dev                          (Vite, порт 5173, проксирует /api)
```
Ожидаем: login под админом (`admin@crm.local`) работает; `/soprovozhdenie` пока рисует PlaceholderPage.

---

## Task 6.3.1 — API-слой `api/support.ts` + widen типов в `api/procedures.ts`

**Files:**
- Create: `frontend/src/api/support.ts`, `frontend/src/api/support.test.ts`
- Modify: `frontend/src/api/procedures.ts` (`ProcedureDetail` +Б2+`deliveries`; `ProcedurePosition` +`delivery_id`; `ProcedurePatch` +Б2)

**Interfaces:**
- Consumes: `apiFetch` из `./client`; backend-схемы `schemas/deliveries.py` + расширенный `schemas/procedures.py`.
- Produces: `SupportSort`, `SupportListItem`, `PaginatedSupport`, `DeliveryOut`, `DeliveryPatch`, `UpdIn`, `UpdOut`, `StatusPostavki`/`STATUS_POSTAVKI`; функции `listSupport`, `createDelivery`, `deleteDelivery`, `patchDelivery`, `upsertUpd`; widened `ProcedureDetail`/`ProcedurePosition`/`ProcedurePatch` (+ `patchProcedure` reuse для Б2).

- [ ] **Шаг 1: widen `api/procedures.ts`** — добавить `delivery_id` в позицию, Б2-поля + `deliveries` в деталь, Б2 в patch. Тип `DeliveryOut` импортируется из нового `./support`.

В `ProcedurePosition` добавить поле (после `price`):
```ts
export type ProcedurePosition = {
  id: number
  procedure_id: number
  source_id: number | null
  name: string
  qty: number
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
  price: number | null // INTEGER kopecks
  delivery_id: number | null // NULL = «ожидает отгрузки» (Фаза 6.2)
}
```
Вверху файла добавить импорт и widen `ProcedureDetail`/`ProcedurePatch`:
```ts
import type { DeliveryOut } from './support'

// ... (после существующих импортов)

export type ProcedureDetail = {
  id: number
  proc: string | null
  tender_id: number
  tender_num: string | null
  parent_id: number
  code: string
  title: string
  mtr: string | null
  supplier: string | null
  fio_zakupshchik: string | null
  pub_start: string | null
  pub_end: string | null
  zagruzka: string
  block: string
  status_zakup: string | null
  // Б2 (Сопровождение, Фаза 6.2):
  contract: string | null
  fio_dogovornik: string | null
  contract_sum: number | null
  status_sdelki: string | null
  status_postavki: string | null
  srok_dd: string | null
  plan_date: string | null
  fakt_date: string | null
  created_at: string
  positions: ProcedurePosition[]
  deliveries: DeliveryOut[]
}

export type ProcedurePatch = {
  proc?: string | null
  tender_num?: string | null
  supplier?: string | null
  fio_zakupshchik?: string | null
  mtr?: string | null
  pub_start?: string | null
  pub_end?: string | null
  status_zakup?: string | null
  // Б2 (Сопровождение):
  contract?: string | null
  fio_dogovornik?: string | null
  contract_sum?: number | null
  status_sdelki?: string | null
  status_postavki?: string | null
  srok_dd?: string | null
  plan_date?: string | null
  fakt_date?: string | null
}
```
> `patchProcedure` (строки 147–155) и `getProcedure` (143–145) **не меняются** — transport тот же; бэкенд block-scoped. SupportCard переиспользует `patchProcedure` для Б2.

- [ ] **Шаг 2: failing test** — `frontend/src/api/support.test.ts` (pure: `buildQuery` сериализация).
```ts
import { describe, it, expect } from 'vitest'

// buildQuery не экспортируется наружу — тестируем через listSupport-подобную
// обёртку невозможно без мока fetch; поэтому экспортируем buildQuery ради теста.
import { buildQuery } from './support'

describe('buildQuery', () => {
  it('skips undefined / null / empty', () => {
    expect(buildQuery({ a: undefined, b: null, c: '', d: 0, e: false })).toBe('?d=0&e=false')
  })
  it('serializes strings/numbers/booleans', () => {
    expect(buildQuery({ search: 'Т-67', page: 2, include_archived: true })).toBe(
      '?search=T-67&page=2&include_archived=true',
    )
  })
  it('returns empty string when nothing to send', () => {
    expect(buildQuery({})).toBe('')
    expect(buildQuery({ x: undefined })).toBe('')
  })
})
```
- [ ] **Шаг 3: run → FAIL** (`buildQuery` не определён). `cd frontend && npx vitest run src/api/support.test.ts` → ImportError.
- [ ] **Шаг 4: implementation** — `frontend/src/api/support.ts`:
```ts
import { apiFetch } from './client'

// Зеркало backend schemas/deliveries.py (Фаза 6.2) + SupportListItem (support.py).

// ---- Helpers --------------------------------------------------------------

/** Сериализует params в querystring, пропуская undefined/null/''. Pure. */
export function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

// ---- Types ----------------------------------------------------------------

export const STATUS_POSTAVKI = [
  'Новая',
  'В производстве',
  'В поставке',
  'Частично поставлено',
  'Поставлено',
  'Отменена',
] as const
export type StatusPostavki = (typeof STATUS_POSTAVKI)[number]

// Whitelist sort-ключей бэкенда GET /support (_SORT_KEYS в support.py):
export type SupportSort =
  | 'created_at'
  | 'code'
  | 'proc'
  | 'supplier'
  | 'contract_sum'
  | 'status_postavki'
  | 'status_sdelki'
  | 'srok_dd'
  | 'plan_date'
  | 'fakt_date'

export type DocsAggregate = { ttn: boolean; m15: boolean; upd: boolean; sert: boolean }

export type SupportListItem = {
  id: number
  proc: string | null
  tender_num: string | null
  code: string
  title: string
  mtr: string | null
  supplier: string | null
  contract: string | null
  contract_sum: number | null
  status_sdelki: string | null
  status_postavki: string | null
  srok_dd: string | null
  plan_date: string | null
  fakt_date: string | null
  is_overdue: boolean
  overdue_pct: number
  docs: DocsAggregate
  progress_delivered: number
  progress_total: number
  created_at: string
}

export type PaginatedSupport = { items: SupportListItem[]; total: number }

export type DeliveryStatus = 'transit' | 'done'

export type UpdOut = { upd: string; pay_status: string } | null

export type DeliveryOut = {
  id: number
  n: number
  status: DeliveryStatus
  date: string | null
  eta: string | null
  doc_ttn: number // 0 | 1
  doc_m15: number
  doc_upd: number
  doc_sert: number
  upd: UpdOut
}

export type DeliveryCreate = { positions: number[] } // ≥1 (бэкенд 422 на пустой)

export type DeliveryPatch = {
  status?: DeliveryStatus // 'done' (transit→done one-way)
  date?: string | null
  eta?: string | null
  doc_ttn?: number
  doc_m15?: number
  doc_upd?: number
  doc_sert?: number
}

export type UpdIn = { upd: string }

// ---- Endpoints ------------------------------------------------------------

export function listSupport(params: {
  include_archived?: boolean
  search?: string
  sort?: SupportSort
  page?: number
  page_size?: number
} = {}): Promise<PaginatedSupport> {
  return apiFetch<PaginatedSupport>(`/support${buildQuery(params)}`)
}

export function createDelivery(
  procedureId: number,
  payload: DeliveryCreate,
): Promise<DeliveryOut> {
  return apiFetch<DeliveryOut>(`/procedures/${procedureId}/deliveries`, {
    method: 'POST',
    body: payload,
  })
}

export function deleteDelivery(id: number): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/deliveries/${id}`, { method: 'DELETE' })
}

export function patchDelivery(id: number, payload: DeliveryPatch): Promise<DeliveryOut> {
  return apiFetch<DeliveryOut>(`/deliveries/${id}`, { method: 'PATCH', body: payload })
}

export function upsertUpd(deliveryId: number, payload: UpdIn): Promise<UpdOut> {
  return apiFetch<UpdOut>(`/deliveries/${deliveryId}/upd`, { method: 'POST', body: payload })
}
```
- [ ] **Шаг 5: run → PASS.** `cd frontend && npx vitest run src/api/support.test.ts` → 3 PASS.
- [ ] **Шаг 6: tsc.** `cd frontend && npx tsc --noEmit` → 0 errors (типы согласованы: `procedures.ts` импортирует `DeliveryOut`, `support.ts` определяет).
- [ ] **Шаг 7: commit.**
```bash
git add frontend/src/api/support.ts frontend/src/api/support.test.ts frontend/src/api/procedures.ts
git commit -m "feat(support-fe): api/support.ts + widened procedure types for Б2 (Phase 6.3.1)"
```

---

## Task 6.3.2 — Цвета статусов `status_sdelki`/`status_postavki` + `StatusSelect.color` prop

**Files:**
- Modify: `frontend/src/lib/statusColors.ts` (+ 2 функции), `frontend/src/lib/statusColors.test.ts` (+ тесты)
- Modify: `frontend/src/components/StatusSelect.tsx` (+ optional `color` prop)

**Interfaces:**
- Consumes: `ChipKind` из `../components/Chip`.
- Produces: `sdelkiStatusChip(v)`, `postavkiStatusChip(v)` → `{kind, label}`; `StatusSelect` принимает `color?: (v) => {kind, label}` (дефолт `procStatusChip`).

- [ ] **Шаг 1: failing tests** — добавить в `frontend/src/lib/statusColors.test.ts` (если файла нет — создать; он есть, расширить):
```ts
import { describe, it, expect } from 'vitest'
import { sdelkiStatusChip, postavkiStatusChip } from './statusColors'

describe('sdelkiStatusChip', () => {
  it('Подписано → ok', () => {
    expect(sdelkiStatusChip('Подписано')).toEqual({ kind: 'ok', label: 'Подписано' })
  })
  it('Подготовка ДД → teal', () => {
    expect(sdelkiStatusChip('Подготовка ДД')).toEqual({ kind: 'teal', label: 'Подготовка ДД' })
  })
  it('Согласование → wait', () => {
    expect(sdelkiStatusChip('Согласование')).toEqual({ kind: 'wait', label: 'Согласование' })
  })
  it('null/empty → wait «Не задано»', () => {
    expect(sdelkiStatusChip(null)).toEqual({ kind: 'wait', label: 'Не задано' })
    expect(sdelkiStatusChip('')).toEqual({ kind: 'wait', label: 'Не задано' })
  })
  it('unknown → proc fallback', () => {
    expect(sdelkiStatusChip('Чтото')).toEqual({ kind: 'proc', label: 'Чтото' })
  })
})

describe('postavkiStatusChip', () => {
  it('Отменена → late (red, единственный красный)', () => {
    expect(postavkiStatusChip('Отменена')).toEqual({ kind: 'late', label: 'Отменена' })
  })
  it('Поставлено → ok', () => {
    expect(postavkiStatusChip('Поставлено')).toEqual({ kind: 'ok', label: 'Поставлено' })
  })
  it('Частично поставлено → pay', () => {
    expect(postavkiStatusChip('Частично поставлено')).toEqual({ kind: 'pay', label: 'Частично поставлено' })
  })
  it('В поставке → supp', () => {
    expect(postavkiStatusChip('В поставке')).toEqual({ kind: 'supp', label: 'В поставке' })
  })
  it('В производстве → teal', () => {
    expect(postavkiStatusChip('В производстве')).toEqual({ kind: 'teal', label: 'В производстве' })
  })
  it('Новая → wait', () => {
    expect(postavkiStatusChip('Новая')).toEqual({ kind: 'wait', label: 'Новая' })
  })
  it('null/empty → wait «Не задано»', () => {
    expect(postavkiStatusChip(null)).toEqual({ kind: 'wait', label: 'Не задано' })
  })
  it('unknown → proc fallback', () => {
    expect(postavkiStatusChip('???')).toEqual({ kind: 'proc', label: '???' })
  })
})
```
- [ ] **Шаг 2: run → FAIL.** `cd frontend && npx vitest run src/lib/statusColors.test.ts` → функции не экспортируются.
- [ ] **Шаг 3: implementation** — добавить в конец `frontend/src/lib/statusColors.ts`:
```ts
/**
 * status_sdelki → { chip kind, label }. Pure; unit-tested.
 * Значения — из dict kind 'status_sdelki' (3 значения). RED не используется.
 * - NULL / "" → wait (gray), «Не задано».
 * - Подписано → ok; Подготовка ДД → teal; Согласование → wait.
 * - иное → proc fallback.
 */
export function sdelkiStatusChip(
  v: string | null | undefined,
): { kind: ChipKind; label: string } {
  if (!v || v === '') return { kind: 'wait', label: 'Не задано' }
  switch (v) {
    case 'Подписано':
      return { kind: 'ok', label: v }
    case 'Подготовка ДД':
      return { kind: 'teal', label: v }
    case 'Согласование':
      return { kind: 'wait', label: v }
    default:
      return { kind: 'proc', label: v }
  }
}

/**
 * status_postavki → { chip kind, label }. Pure; unit-tested.
 * 6-значный enum. RED (late) — только «Отменена» (консистентно с status_zakup).
 * - NULL / "" → wait (gray), «Не задано».
 * - иное → proc fallback.
 */
export function postavkiStatusChip(
  v: string | null | undefined,
): { kind: ChipKind; label: string } {
  if (!v || v === '') return { kind: 'wait', label: 'Не задано' }
  switch (v) {
    case 'Отменена':
      return { kind: 'late', label: v }
    case 'Поставлено':
      return { kind: 'ok', label: v }
    case 'Частично поставлено':
      return { kind: 'pay', label: v }
    case 'В поставке':
      return { kind: 'supp', label: v }
    case 'В производстве':
      return { kind: 'teal', label: v }
    case 'Новая':
      return { kind: 'wait', label: v }
    default:
      return { kind: 'proc', label: v }
  }
}
```
- [ ] **Шаг 4: run → PASS.** `cd frontend && npx vitest run src/lib/statusColors.test.ts` → all PASS (новые + существующий procStatusChip).
- [ ] **Шаг 5: generalize `StatusSelect`** — `frontend/src/components/StatusSelect.tsx`. Добавить optional `color` prop (дефолт `procStatusChip`); заменить **оба** вызова `procStatusChip(...)` на `color(...)`.

Сигнатура (строки 21–31) — заменить:
```ts
export function StatusSelect({
  value,
  options,
  onSelect,
  disabled = false,
  color = procStatusChip,
}: {
  value: string | null | undefined
  options: string[]
  onSelect: (status: string) => void
  disabled?: boolean
  color?: (v: string | null | undefined) => { kind: ChipKind; label: string }
}) {
```
Строка 72 (`const cur = procStatusChip(value)`) → `const cur = color(value)`.
Строка 121 (`const k = procStatusChip(v).kind`) → `const k = color(v).kind`.
Добавить импорт `ChipKind`: `import { procStatusChip } from '../lib/statusColors'` → `import { procStatusChip } from '../lib/statusColors'\nimport type { ChipKind } from './Chip'`.
> Регрессия: `Zakupka` зовёт `<StatusSelect .../>` без `color` → дефолт `procStatusChip`, поведение идентично. ui-checker на STOP (6.3.4) подтвердит.
- [ ] **Шаг 6: tsc + tests.** `cd frontend && npx tsc --noEmit && npx vitest run` → 0 errors, all PASS.
- [ ] **Шаг 7: commit.**
```bash
git add frontend/src/lib/statusColors.ts frontend/src/lib/statusColors.test.ts frontend/src/components/StatusSelect.tsx
git commit -m "feat(support-fe): sdelki/postavki chip colors + StatusSelect.color prop (Phase 6.3.2)"
```

---

## Task 6.3.3 — Pure helpers `lib/supportView.ts` + presentational-компоненты `components/support/*`

**Files:**
- Create: `frontend/src/lib/supportView.ts`, `frontend/src/lib/supportView.test.ts`
- Create: `frontend/src/components/support/OverduePct.tsx`, `Progress.tsx`, `DocsSquares.tsx`, `DocToggle.tsx`, `PayChip.tsx`

**Interfaces:**
- Consumes: `ProcedurePosition` (для `sumPositionsKopecks`), `DeliveryOut`/`DocsAggregate`.
- Produces: `overdueMod(pct)`, `progressState(delivered, total)`, `sumPositionsKopecks(positions)`, `sisterRoute(block, id)`; компоненты `OverduePct`, `Progress`, `DocsSquares`, `DocToggle`, `PayChip`.

- [ ] **Шаг 1: failing tests** — `frontend/src/lib/supportView.test.ts`:
```ts
import { describe, it, expect } from 'vitest'
import {
  overdueMod,
  progressState,
  sumPositionsKopecks,
  sisterRoute,
} from './supportView'

describe('overdueMod', () => {
  it('0 → green (base)', () => expect(overdueMod(0)).toBe(''))
  it('>0 and <50 → orange (w)', () => {
    expect(overdueMod(1)).toBe(' w')
    expect(overdueMod(49.9)).toBe(' w')
  })
  it('>=50 → red (b)', () => {
    expect(overdueMod(50)).toBe(' b')
    expect(overdueMod(100)).toBe(' b')
  })
  it('negative → green', () => expect(overdueMod(-5)).toBe(''))
})

describe('progressState', () => {
  it('zero total → 0%, not done', () => {
    expect(progressState(0, 0)).toEqual({ pct: 0, done: false })
  })
  it('none delivered → 0%', () => {
    expect(progressState(0, 3)).toEqual({ pct: 0, done: false })
  })
  it('partial → pct, not done', () => {
    const r = progressState(1, 3)
    expect(r.done).toBe(false)
    expect(Math.round(r.pct)).toBe(33)
  })
  it('all delivered → 100%, done', () => {
    expect(progressState(2, 2)).toEqual({ pct: 100, done: true })
  })
})

describe('sumPositionsKopecks', () => {
  it('sums qty*price (kopecks), price null → 0', () => {
    expect(
      sumPositionsKopecks([
        { qty: 2, price: 10000 },
        { qty: 1, price: null },
        { qty: 1.5, price: 5000 },
      ]),
    ).toBe(27500) // 2*100.00 + 0 + 1.5*50.00
  })
  it('empty → 0', () => expect(sumPositionsKopecks([])).toBe(0))
})

describe('sisterRoute', () => {
  it('soprovozhdenie → /soprovozhdenie/:id', () => {
    expect(sisterRoute('soprovozhdenie', 42)).toBe('/soprovozhdenie/42')
  })
  it('zakupka (or other) → /zakupka/:id', () => {
    expect(sisterRoute('zakupka', 7)).toBe('/zakupka/7')
    expect(sisterRoute(null, 7)).toBe('/zakupka/7')
  })
})
```
- [ ] **Шаг 2: run → FAIL.** `cd frontend && npx vitest run src/lib/supportView.test.ts` → ImportError.
- [ ] **Шаг 3: implementation** — `frontend/src/lib/supportView.ts`:
```ts
/** Pure view-логика для страницы/карточки Сопровождения (Фаза 6.3). */

/** Бакет просрочки → CSS-модификатор `.ovd` (база=зелёный) / `.w` / `.b`. */
export function overdueMod(overduePct: number): '' | ' w' | ' b' {
  if (overduePct >= 50) return ' b'
  if (overduePct > 0) return ' w'
  return ''
}

/** Состояние прогресса поставки. done = все позиции получены. */
export function progressState(
  delivered: number,
  total: number,
): { pct: number; done: boolean } {
  const t = Math.max(0, Math.floor(total))
  const d = Math.max(0, Math.floor(delivered))
  if (t === 0) return { pct: 0, done: false }
  return { pct: Math.min(100, (d / t) * 100), done: d >= t }
}

/** Σ qty*price (копейки); price null → 0. Для подсказки «Σ позиций» у суммы договора. */
export function sumPositionsKopecks(
  positions: { qty: number; price: number | null }[],
): number {
  let s = 0
  for (const p of positions) {
    if (p.price != null) s += Math.round(p.qty * p.price)
  }
  return s
}

/** Маршрут сестры-процедуры per-block. block есть в ProcedureOut (api/requests.ts). */
export function sisterRoute(block: string | null | undefined, id: number): string {
  return block === 'soprovozhdenie' ? `/soprovozhdenie/${id}` : `/zakupka/${id}`
}
```
- [ ] **Шаг 4: run → PASS.** `cd frontend && npx vitest run src/lib/supportView.test.ts` → all PASS.
- [ ] **Шаг 5: presentational-компоненты** — каждый эмитит существующий CSS (новых стилей нет). Создать 5 файлов в `frontend/src/components/support/`.

`OverduePct.tsx`:
```tsx
import { overdueMod } from '../../lib/supportView'

/** Пилюля просрочки: `.ovd` (зелёный 0%) / `.w` (оранжевый 1–49%) / `.b` (красный ≥50%). */
export function OverduePct({ overduePct }: { overduePct: number }) {
  const pct = Math.round(overduePct)
  return <span className={`ovd${overdueMod(overduePct)}`}>{pct}%</span>
}
```

`Progress.tsx`:
```tsx
import { progressState } from '../../lib/supportView'

/** Прогресс поставки: `.prog` + `.bar i` (ширина %), `.done` когда всё получено. */
export function Progress({ delivered, total }: { delivered: number; total: number }) {
  const { pct, done } = progressState(delivered, total)
  return (
    <div className={`prog${done ? ' done' : ''}`}>
      <div className="bar">
        <i style={{ width: `${pct}%` }} />
      </div>
      <span className="pn">
        <b>{delivered}</b>/{total}
      </span>
    </div>
  )
}
```

`DocsSquares.tsx`:
```tsx
import type { DocsAggregate } from '../../api/support'

/** 4 квадрата ТТН/М-15/УПД/Серт. Зелёный = есть, красный (.no) = нет. */
const ENTRIES: { key: keyof DocsAggregate; label: string }[] = [
  { key: 'ttn', label: 'ТТН' },
  { key: 'm15', label: 'М-15' },
  { key: 'upd', label: 'УПД' },
  { key: 'sert', label: 'Серт' },
]

export function DocsSquares({ docs }: { docs: DocsAggregate }) {
  return (
    <span className="docsq">
      {ENTRIES.map((e) => (
        <span key={e.key} className={docs[e.key] ? '' : 'no'} title={e.label}>
          {e.label}
        </span>
      ))}
    </span>
  )
}
```

`DocToggle.tsx`:
```tsx
/** Переключатель документа в поставке: `.doctag` (✓ зелёный, on) / `.no` (✕ красный, off). */
export function DocToggle({
  label,
  on,
  disabled,
  onClick,
}: {
  label: string
  on: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`doctag${on ? '' : ' no'}`}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      disabled={disabled}
      style={{ border: 'none', cursor: disabled ? 'default' : 'pointer', fontFamily: 'inherit' }}
    >
      {label}
    </button>
  )
}
```

`PayChip.tsx`:
```tsx
/** Статус оплаты УПД: `.pchip` + `.await` (Ожидает) / `.paid` (Оплачено) / `.late` (иное). */
const MAP: Record<string, { cls: string; label: string }> = {
  await: { cls: 'await', label: 'Ожидает оплаты' },
  paid: { cls: 'paid', label: 'Оплачено' },
}
export function PayChip({ payStatus }: { payStatus: string | null | undefined }) {
  if (!payStatus) return null
  const m = MAP[payStatus] ?? { cls: 'late', label: payStatus }
  return <span className={`pchip ${m.cls}`}>{m.label}</span>
}
```
- [ ] **Шаг 6: tsc.** `cd frontend && npx tsc --noEmit` → 0 errors.
- [ ] **Шаг 7: commit.**
```bash
git add frontend/src/lib/supportView.ts frontend/src/lib/supportView.test.ts frontend/src/components/support
git commit -m "feat(support-fe): pure view helpers + DocsSquares/OverduePct/Progress/DocToggle/PayChip (Phase 6.3.3)"
```

---

## Task 6.3.4 — Страница «В сопровождении» + маршрут + tab-counter

**Files:**
- Create: `frontend/src/pages/Soprovozhdenie.tsx`
- Modify: `frontend/src/App.tsx` (route `/soprovozhdenie` → `Soprovozhdenie`), `frontend/src/components/Tabs.tsx` (counter)

**Interfaces:**
- Consumes: `listSupport`, `patchProcedure`, `listDict`, `STATUS_POSTAVKI`, `sdelkiStatusChip`/`postavkiStatusChip`, `StatusSelect`, `DataTable`, `FilterBar`, `EmptyState`, `money`/`dateRu`, `OverduePct`/`Progress`/`DocsSquares`, `canEdit`, `useDebounced` (локальный хук, копия из `Zakupka.tsx`).
- Produces: `<Soprovozhdenie/>` — список с in-row правкой Б2 + производными колонками.

> **Паттерн — копия `Zakupka.tsx`** (FilterBar + `.block` с `--bc:var(--supp)` + `.tbl-scroll` > `DataTable` + `useDebounced` + `buildColumns` factory в `useMemo`). Ширины колонок суммируются в 100% (fixed layout).

- [ ] **Шаг 1: implementation** — `frontend/src/pages/Soprovozhdenie.tsx`:
```tsx
import { useMemo, useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listSupport, STATUS_POSTAVKI, type SupportListItem, type SupportSort } from '../api/support'
import { listDict } from '../api/dict'
import { patchProcedure, type ProcedurePatch } from '../api/procedures'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { StatusSelect } from '../components/StatusSelect'
import { Chip } from '../components/Chip'
import { OverduePct } from '../components/support/OverduePct'
import { Progress } from '../components/support/Progress'
import { DocsSquares } from '../components/support/DocsSquares'
import { sdelkiStatusChip, postavkiStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

type Numbered = SupportListItem & { _idx: number }

const SORT_OPTIONS: { value: SupportSort; label: string }[] = [
  { value: 'created_at', label: 'По дате создания' },
  { value: 'code', label: 'По коду' },
  { value: 'proc', label: 'По № процедуры' },
  { value: 'supplier', label: 'По поставщику' },
  { value: 'contract_sum', label: 'По сумме договора' },
  { value: 'status_postavki', label: 'По статусу поставки' },
  { value: 'status_sdelki', label: 'По статусу сделки' },
  { value: 'srok_dd', label: 'По сроку ДД' },
  { value: 'plan_date', label: 'По плану' },
  { value: 'fakt_date', label: 'По факту' },
]

function useDebounced<T>(value: T, delay: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return v
}

function buildColumns(args: {
  sdelkiOptions: string[] | null
  onSdelki: (id: number, v: string) => void
  onPostavki: (id: number, v: string) => void
  onDate: (id: number, field: 'plan_date' | 'fakt_date', v: string) => void
  canEdit: boolean
}): DataTableColumn<Numbered>[] {
  const { sdelkiOptions, onSdelki, onPostavki, onDate, canEdit } = args
  return [
    { key: '#', header: '#', width: '3%', render: (r) => r._idx + 1 },
    {
      key: 'title',
      header: 'Наименование',
      width: '16%',
      render: (r) => (
        <span>
          <span className="tnum" style={{ color: 'var(--supp)', fontWeight: 600 }}>
            {r.code}
          </span>{' '}
          {r.title}
        </span>
      ),
    },
    { key: 'tender_num', header: '№ заявки', width: '6%', render: (r) => r.tender_num ?? '—' },
    { key: 'proc', header: '№ процед.', width: '5%', render: (r) => r.proc ?? '—' },
    { key: 'supplier', header: 'Поставщик', width: '8%', render: (r) => r.supplier ?? '—' },
    { key: 'mtr', header: 'Тип МТР', width: '7%', render: (r) => r.mtr ?? '—' },
    { key: 'contract_sum', header: 'Сумма дог.', width: '8%', align: 'right', render: (r) => money(r.contract_sum) },
    {
      key: 'status_sdelki',
      header: 'Статус сделки',
      width: '9%',
      render: (r) =>
        canEdit ? (
          <StatusSelect
            value={r.status_sdelki}
            options={sdelkiOptions ?? []}
            onSelect={(v) => onSdelki(r.id, v)}
            color={sdelkiStatusChip}
          />
        ) : (
          <Chip {...sdelkiStatusChip(r.status_sdelki)} mini />
        ),
    },
    {
      key: 'status_postavki',
      header: 'Статус поставки',
      width: '9%',
      render: (r) =>
        canEdit ? (
          <StatusSelect
            value={r.status_postavki}
            options={[...STATUS_POSTAVKI]}
            onSelect={(v) => onPostavki(r.id, v)}
            color={postavkiStatusChip}
          />
        ) : (
          <Chip {...postavkiStatusChip(r.status_postavki)} mini />
        ),
    },
    { key: 'srok_dd', header: 'Срок ДД', width: '6%', render: (r) => <span className="dt">{dateRu(r.srok_dd)}</span> },
    {
      key: 'plan_date',
      header: 'План',
      width: '6%',
      render: (r) =>
        canEdit ? (
          <input
            type="date"
            value={r.plan_date ?? ''}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onDate(r.id, 'plan_date', e.target.value)}
            style={{ border: '1px solid var(--line)', borderRadius: 4, padding: '2px 4px', fontFamily: 'inherit', fontSize: 12 }}
          />
        ) : (
          <span className="dt">{dateRu(r.plan_date)}</span>
        ),
    },
    {
      key: 'fakt_date',
      header: 'Факт',
      width: '6%',
      render: (r) =>
        canEdit ? (
          <input
            type="date"
            value={r.fakt_date ?? ''}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onDate(r.id, 'fakt_date', e.target.value)}
            style={{ border: '1px solid var(--line)', borderRadius: 4, padding: '2px 4px', fontFamily: 'inherit', fontSize: 12 }}
          />
        ) : (
          <span className="dt">{dateRu(r.fakt_date)}</span>
        ),
    },
    { key: 'overdue_pct', header: 'Просроч.', width: '5%', render: (r) => <OverduePct overduePct={r.overdue_pct} /> },
    { key: 'docs', header: 'Док-ты', width: '6%', render: (r) => <DocsSquares docs={r.docs} /> },
    {
      key: 'progress',
      header: 'Поз.',
      width: '6%',
      render: (r) => <Progress delivered={r.progress_delivered} total={r.progress_total} />,
    },
  ]
}

export function Soprovozhdenie() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')

  const [searchInput, setSearchInput] = useState('')
  const [nonSearch, setNonSearch] = useState<{ include_archived: boolean; sort: SupportSort }>({
    include_archived: false,
    sort: 'created_at',
  })
  const debouncedSearch = useDebounced(searchInput, 300)

  const list = useQuery({
    queryKey: ['support', { search: debouncedSearch, ...nonSearch }],
    queryFn: () =>
      listSupport({
        search: debouncedSearch || undefined,
        include_archived: nonSearch.include_archived || undefined,
        sort: nonSearch.sort,
        page: 1,
        page_size: 100,
      }),
  })

  const sdelkiDict = useQuery({
    queryKey: ['dict', 'status_sdelki'],
    queryFn: () => listDict('status_sdelki'),
  })
  const sdelkiOptions = sdelkiDict.data?.map((d) => d.value) ?? null

  const patchMut = useMutation({
    mutationFn: (vars: { id: number; patch: ProcedurePatch }) =>
      patchProcedure(vars.id, vars.patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['support'] }),
    onError: (err) => console.error('support patch failed', err),
  })
  const onSdelki = useCallback((id: number, v: string) => patchMut.mutate({ id, patch: { status_sdelki: v } }), [patchMut])
  const onPostavki = useCallback((id: number, v: string) => patchMut.mutate({ id, patch: { status_postavki: v } }), [patchMut])
  const onDate = useCallback(
    (id: number, field: 'plan_date' | 'fakt_date', v: string) =>
      patchMut.mutate({ id, patch: field === 'plan_date' ? { plan_date: v || null } : { fakt_date: v || null } }),
    [patchMut],
  )

  const columns = useMemo(
    () => buildColumns({ sdelkiOptions, onSdelki, onPostavki, onDate, canEdit: canEditThis }),
    [sdelkiOptions, onSdelki, onPostavki, onDate, canEditThis],
  )

  const items = list.data?.items ?? []
  const numbered: Numbered[] = items.map((r, i) => ({ ...r, _idx: i }))
  const total = list.data?.total ?? 0

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>В сопровождении</h1>
        <p className="desc">Процедуры после закупки: договор, поставки, документы, УПД.</p>
      </div>

      <FilterBar>
        <input
          className="search"
          placeholder="Поиск: Т-67, № заявки, поставщик, договор, № УПД…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select value={nonSearch.sort} onChange={(e) => setNonSearch((s) => ({ ...s, sort: e.target.value as SupportSort }))}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label className="chk">
          <input
            type="checkbox"
            checked={nonSearch.include_archived}
            onChange={(e) => setNonSearch((s) => ({ ...s, include_archived: e.target.checked }))}
          />{' '}
          Показать завершённые/отменённые
        </label>
      </FilterBar>

      <div className="block reg" style={{ ['--bc' as any]: 'var(--supp)' }}>
        <div className="block-h">
          <span className="bnum">С</span>
          <span className="btitle">В сопровождении</span>
          <span className="bcount">{total}</span>
        </div>
        <div className="tbl-scroll">
          <DataTable<Numbered>
            columns={columns}
            rows={numbered}
            getRowId={(r) => r.id}
            onRowClick={(row) => navigate(`/soprovozhdenie/${row.id}`)}
            empty={
              <EmptyState
                title={list.isError ? 'Ошибка загрузки' : 'Нет процедур в сопровождении'}
                hint={list.isError ? 'Проверьте подключение к серверу.' : 'Процедуры появятся после «Передать в сопровождение» в закупке.'}
              />
            }
          />
        </div>
      </div>
    </div>
  )
}
```
> Если в `Zakupka.tsx` используется иной класс строки/иконки (`bnum`/`btitle`/`chk`/`search`) — скопировать **дословно** оттуда; имена выше соответствуют канону Concept design.
- [ ] **Шаг 2: route** — `frontend/src/App.tsx`. Импорт (после строки 10 `import { Zakupka }`):
```ts
import { Soprovozhdenie } from './pages/Soprovozhdenie'
import { SupportCard } from './cards/SupportCard'
```
Строка 36 `<Route path="/soprovozhdenie" element={<PlaceholderPage title="В сопровождении" />} />` → заменить на:
```tsx
        <Route path="/soprovozhdenie" element={<Soprovozhdenie />} />
        <Route path="/soprovozhdenie/:id" element={<SupportCard />} />
```
> `SupportCard` создаётся в Task 6.3.5a; чтобы `tsc` не падал сейчас — либо выполни 6.3.4→6.3.5a подряд перед `tsc`, либо закомментируй импорт/маршрут `SupportCard` до 6.3.5a. **Рекомендация:** выполняй 6.3.4 и 6.3.5a в одной сессии.
- [ ] **Шаг 3: tab-counter** — `frontend/src/components/Tabs.tsx`. Импорт (строка 4):
```ts
import { listProcurements } from '../api/procedures'
import { listSupport } from '../api/support'
```
После `ZAKUP_COUNTER_KEY` (строка 22):
```ts
const SOPP_COUNTER_KEY = ['support', { tabCounter: true }] as const
```
Внутри `Tabs()` после `const zakup = useQuery(...)` добавить:
```ts
  const sopp = useQuery({
    queryKey: SOPP_COUNTER_KEY,
    queryFn: () => listSupport({ page_size: 1 }),
  })
  const soppTotal = sopp.data?.total
```
Тернарник `count` (строки 39–46) — заменить на:
```ts
        const count =
          t.to === '/komplektaciya'
            ? (komplTotal ?? '—')
            : t.to === '/zakupka'
              ? (zakupTotal ?? '—')
              : t.to === '/soprovozhdenie'
                ? (soppTotal ?? '—')
                : t.showCounter
                  ? '—'
                  : null
```
- [ ] **Шаг 4: tsc.** `cd frontend && npx tsc --noEmit` → 0 errors (с учётом `SupportCard` из 6.3.5a).
- [ ] **Шаг 5: ui-checker (smoke страницы).** Поднять backend+frontend, прогнать агента `ui-checker`: вход под админом → вкладка «В сопровождении» активна, счётчик в табе — число, таблица рендерится, раскладка ≥1280px без горизонтального переполнения контейнера, нет ошибок в консоли/сети. In-row: смена `status_sdelki`/`status_postavki` и дат сохраняется (PATCH 200, строка обновляется); клик по строке → попытка перехода на `/soprovozhdenie/:id` (карточка — в 6.3.5a). Под ролью без прав — контролы только для чтения (chips/текст).
- [ ] **Шаг 6: commit.**
```bash
git add frontend/src/pages/Soprovozhdenie.tsx frontend/src/App.tsx frontend/src/components/Tabs.tsx
git commit -m "feat(support-fe): Soprovozhdenie list page + route + tab counter (Phase 6.3.4)"
```

---

## Task 6.3.5a — `SupportCard` Б2: shell + шапка договора (правка) + sister-switcher + маршрут

**Files:**
- Create: `frontend/src/cards/SupportCard.tsx`

**Interfaces:**
- Consumes: `getProcedure`, `patchProcedure`, `getRequest`, `listDict`, `STATUS_POSTAVKI`, `StatusSelect` (+ `color`), `sdelkiStatusChip`/`postavkiStatusChip`, `money`/`dateRu`/`kopecksToRublesInput`/`rublesToKopecks`, `sumPositionsKopecks`/`sisterRoute`, `canEdit`, `Chip`, `EmptyState`.
- Produces: `<SupportCard/>` — загрузка процедуры, `refresh()`, sister-switcher (per-block), back, **редактируемая шапка договора** (saveAll diff-patch Б2), позиции read-only, плашка «Ожидают отгрузки» (read-only — поставки в 6.3.5b).

> **Паттерн — копия `ProcedureCard.tsx`**: `useQuery(['procedure', id], getProcedure, enabled)`; `refresh()` = await `refetchQueries(['procedure', id])` → `invalidateQueries(['support'])` + `['request', parent_id]` → сброс драфтов; sister-switcher через `getRequest(parent_id).tenders.find(...).procedures`; draft+`saveAll` diff-patch; `lastErrorMessage`; `savedTick`. Позиции — read-only список.

- [ ] **Шаг 1: implementation** — `frontend/src/cards/SupportCard.tsx` (полный файл; секция поставок `<DeliverySection/>` подключается в 6.3.5b — пока «Ожидают отгрузки» read-only):
```tsx
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProcedure, patchProcedure, type ProcedureDetail, type ProcedurePatch } from '../api/procedures'
import { getRequest } from '../api/requests'
import { listDict } from '../api/dict'
import { STATUS_POSTAVKI } from '../api/support'
import { StatusSelect } from '../components/StatusSelect'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import { sdelkiStatusChip, postavkiStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { kopecksToRublesInput, rublesToKopecks } from '../lib/money'
import { sumPositionsKopecks, sisterRoute } from '../lib/supportView'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

type SoppDraft = {
  contract: string
  fio_dogovornik: string
  contract_sum: string // rubles input string
  status_sdelki: string
  status_postavki: string
  srok_dd: string
  plan_date: string
  fakt_date: string
}

function draftFromProc(p: ProcedureDetail): SoppDraft {
  return {
    contract: p.contract ?? '',
    fio_dogovornik: p.fio_dogovornik ?? '',
    contract_sum: kopecksToRublesInput(p.contract_sum),
    status_sdelki: p.status_sdelki ?? '',
    status_postavki: p.status_postavki ?? '',
    srok_dd: p.srok_dd ?? '',
    plan_date: p.plan_date ?? '',
    fakt_date: p.fakt_date ?? '',
  }
}

/** Diff драфта vs процедуры → только изменённые Б2-поля (empty string → null). */
function buildSoppPatch(d: SoppDraft, p: ProcedureDetail): ProcedurePatch | null {
  const patch: ProcedurePatch = {}
  const cur = draftFromProc(p)
  const setStr = (field: keyof ProcedurePatch, dk: keyof SoppDraft) => {
    if (d[dk] !== cur[dk]) (patch as any)[field] = d[dk] === '' ? null : d[dk]
  }
  setStr('contract', 'contract')
  setStr('fio_dogovornik', 'fio_dogovornik')
  setStr('status_sdelki', 'status_sdelki')
  setStr('status_postavki', 'status_postavki')
  setStr('srok_dd', 'srok_dd')
  setStr('plan_date', 'plan_date')
  setStr('fakt_date', 'fakt_date')
  // money round-trip (как price в ProcedureCard):
  if (rublesToKopecks(d.contract_sum) !== p.contract_sum) {
    patch.contract_sum = rublesToKopecks(d.contract_sum)
  }
  return Object.keys(patch).length ? patch : null
}

function lastErrorMessage(err: unknown): string {
  const e = err as { body?: { detail?: string } } | null
  return e?.body?.detail ?? 'Не удалось сохранить'
}

const fieldStyle: React.CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: 6,
  padding: '6px 8px',
  fontFamily: 'inherit',
  fontSize: 13,
  width: '100%',
}
const labelStyle: React.CSSProperties = { fontSize: 11, color: 'var(--muted)', marginBottom: 3, display: 'block' }

export function SupportCard() {
  const { id } = useParams()
  const procedureId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')

  const procQ = useQuery({
    queryKey: ['procedure', procedureId],
    queryFn: () => getProcedure(procedureId),
    enabled: Number.isFinite(procedureId),
  })
  const proc = procQ.data

  const parentQ = useQuery({
    queryKey: ['request', proc?.parent_id],
    queryFn: () => getRequest(proc!.parent_id),
    enabled: !!proc,
  })

  const sdelkiDict = useQuery({
    queryKey: ['dict', 'status_sdelki'],
    queryFn: () => listDict('status_sdelki'),
  })
  const sdelkiOptions = sdelkiDict.data?.map((d) => d.value) ?? []

  const [draft, setDraft] = useState<SoppDraft | null>(null)
  const [savedTick, setSavedTick] = useState(0)
  const [actionErr, setActionErr] = useState<string | null>(null)

  // reset draft on procedure change (sister-switcher) / load
  useEffect(() => {
    setDraft(null)
    setActionErr(null)
  }, [procedureId])

  const refresh = useCallback(async () => {
    await qc.refetchQueries({ queryKey: ['procedure', procedureId] })
    qc.invalidateQueries({ queryKey: ['support'] })
    if (proc?.parent_id) qc.invalidateQueries({ queryKey: ['request', proc.parent_id] })
    setDraft(null)
  }, [qc, procedureId, proc?.parent_id])

  const saveMut = useMutation({
    mutationFn: (payload: ProcedurePatch) => patchProcedure(procedureId, payload),
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

  if (procQ.isLoading) return <div className="wrap"><p className="desc">Загрузка…</p></div>
  if (procQ.isError || !proc)
    return (
      <div className="wrap">
        <EmptyState title="Процедура не найдена" hint="Возможно, она удалена или нет прав." />
      </div>
    )

  const d = draft ?? draftFromProc(proc)
  const patch = draft ? buildSoppPatch(draft, proc) : null
  const sisters =
    parentQ.data?.tenders.find((t) => t.id === proc.tender_id)?.procedures ?? []
  const positionsSum = sumPositionsKopecks(proc.positions)
  const awaiting = proc.positions.filter((p) => p.delivery_id == null)

  function setField<K extends keyof SoppDraft>(k: K, v: SoppDraft[K]) {
    setDraft((prev) => ({ ...(prev ?? draftFromProc(proc!)), [k]: v }))
  }

  return (
    <div className="wrap">
      <div className="page-h">
        <button className="btn" onClick={() => navigate('/soprovozhdenie')}>
          ← В сопровождении
        </button>
        <h1>
          <span className="tnum" style={{ color: 'var(--supp)' }}>{proc.code}</span> {proc.title}
        </h1>
      </div>

      {/* Sister switcher (per-block routing) */}
      {sisters.length > 1 && (
        <div className="sisters" style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
          {sisters.map((s) => (
            <button
              key={s.id}
              className={`chip proc mini${s.id === proc.id ? '' : ''}`}
              style={{
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit',
                opacity: s.id === proc.id ? 1 : 0.6,
                fontWeight: s.id === proc.id ? 700 : 400,
              }}
              onClick={() => navigate(sisterRoute(s.block, s.id))}
            >
              №{s.proc ?? s.id}
            </button>
          ))}
        </div>
      )}

      <div className="block reg" style={{ ['--bc' as any]: 'var(--supp)' }}>
        <div className="block-h">
          <span className="bnum">Б2</span>
          <span className="btitle">Сопровождение</span>
          <span className="sp" style={{ flex: 1 }} />
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
          {actionErr && <span style={{ color: 'var(--late)', fontSize: 12 }}>{actionErr}</span>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, padding: 12 }}>
          <div>
            <span style={labelStyle}>№ заявки</span>
            <div style={fieldStyle}>{proc.tender_num ?? '—'}</div>
          </div>
          <div>
            <span style={labelStyle}>№ процедуры</span>
            <div style={fieldStyle}>{proc.proc ?? '—'}</div>
          </div>
          <div>
            <span style={labelStyle}>Поставщик</span>
            <div style={fieldStyle}>{proc.supplier ?? '—'}</div>
          </div>

          <div>
            <span style={labelStyle}>Договор</span>
            <input
              style={fieldStyle}
              disabled={!canEditThis}
              value={d.contract}
              onChange={(e) => setField('contract', e.target.value)}
            />
          </div>
          <div>
            <span style={labelStyle}>ФИО договорника</span>
            <input
              style={fieldStyle}
              disabled={!canEditThis}
              value={d.fio_dogovornik}
              onChange={(e) => setField('fio_dogovornik', e.target.value)}
            />
          </div>
          <div>
            <span style={labelStyle}>Сумма договора (₽)</span>
            <input
              style={fieldStyle}
              disabled={!canEditThis}
              value={d.contract_sum}
              inputMode="decimal"
              onChange={(e) => setField('contract_sum', e.target.value)}
            />
            <span style={{ ...labelStyle, marginTop: 2 }}>Σ позиций: {money(positionsSum)}</span>
          </div>

          <div>
            <span style={labelStyle}>Статус сделки</span>
            {canEditThis ? (
              <StatusSelect
                value={d.status_sdelki}
                options={sdelkiOptions}
                onSelect={(v) => setField('status_sdelki', v)}
                color={sdelkiStatusChip}
              />
            ) : (
              <Chip {...sdelkiStatusChip(d.status_sdelki)} mini />
            )}
          </div>
          <div>
            <span style={labelStyle}>Статус поставки</span>
            {canEditThis ? (
              <StatusSelect
                value={d.status_postavki}
                options={[...STATUS_POSTAVKI]}
                onSelect={(v) => setField('status_postavki', v)}
                color={postavkiStatusChip}
              />
            ) : (
              <Chip {...postavkiStatusChip(d.status_postavki)} mini />
            )}
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <label style={{ flex: 1 }}>
              <span style={labelStyle}>Срок ДД</span>
              <input type="date" style={fieldStyle} disabled={!canEditThis} value={d.srok_dd} onChange={(e) => setField('srok_dd', e.target.value)} />
            </label>
            <label style={{ flex: 1 }}>
              <span style={labelStyle}>План</span>
              <input type="date" style={fieldStyle} disabled={!canEditThis} value={d.plan_date} onChange={(e) => setField('plan_date', e.target.value)} />
            </label>
            <label style={{ flex: 1 }}>
              <span style={labelStyle}>Факт</span>
              <input type="date" style={fieldStyle} disabled={!canEditThis} value={d.fakt_date} onChange={(e) => setField('fakt_date', e.target.value)} />
            </label>
          </div>
        </div>
      </div>

      {/* Позиции — read-only (в Б2 позиции не редактируются, только уходят в поставки) */}
      <div className="block reg" style={{ ['--bc' as any]: 'var(--supp)' }}>
        <div className="block-h">
          <span className="btitle">Позиции процедуры ({proc.positions.length})</span>
        </div>
        <div className="tbl-scroll">
          <table className="postbl">
            <thead>
              <tr>
                <th>Наименование</th>
                <th>Кол-во</th>
                <th>Ед.</th>
                <th>Цена с НДС</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {proc.positions.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.qty}</td>
                  <td>{p.unit ?? '—'}</td>
                  <td>{money(p.price)}</td>
                  <td>{money(p.price != null ? Math.round(p.qty * p.price) : null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ожидают отгрузки — read-only в 6.3.5a; интерактив (Создать поставку) подключается в 6.3.5b */}
      <div className="block reg" style={{ ['--bc' as any]: 'var(--supp)' }}>
        <div className="block-h">
          <span className="btitle">Ожидают отгрузки ({awaiting.length})</span>
        </div>
        <div style={{ padding: 12 }}>
          {awaiting.length === 0 ? (
            <EmptyState title="Все позиции в поставках" />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {awaiting.map((p) => (
                <li key={p.id}>{p.name} — {p.qty} {p.unit ?? ''}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Поставки — подключается в Task 6.3.5b (<DeliverySection/>) */}
    </div>
  )
}
```
> Если `ProcedureCard.tsx` использует хук/стиль для «Сохранить»/sisters иначе — выровнять дословно. В `tsconfig` включён `noUnusedLocals` — не оставлять неиспользуемые импорты.
- [ ] **Шаг 2: tsc.** `cd frontend && npx tsc --noEmit` → 0 errors.
- [ ] **Шаг 3: ui-checker (карточка, шапка).** Открыть процедуру в `/soprovozhdenie/:id` (довести заявку до support через закупку): шапка Б2 рисуется, правка договора/ФИО/суммы/статусов/дат → «Сохранить» → PATCH 200 → значения сохраняются (обновить страницу — на месте). Σ позиций совпадает с введённой суммой. Sister-switcher (если ≥2 сестёр) ведёт по правильному маршруту. Под ролью без прав — поля read-only, кнопки «Сохранить» нет.
- [ ] **Шаг 4: commit.**
```bash
git add frontend/src/cards/SupportCard.tsx
git commit -m "feat(support-fe): SupportCard Б2 shell + contract header editing + sisters (Phase 6.3.5a)"
```

---

## Task 6.3.5b — Секция «Поставки» (создание / документы / получение / расформирование) + № УПД

**Files:**
- Create: `frontend/src/components/support/DeliverySection.tsx`
- Modify: `frontend/src/cards/SupportCard.tsx` (рендер `<DeliverySection/>`)

**Interfaces:**
- Consumes: `createDelivery`, `deleteDelivery`, `patchDelivery`, `upsertUpd`, `ProcedureDetail`, `Modal`, `DocToggle`, `PayChip`, `money`/`dateRu`, `canEdit`.
- Produces: `<DeliverySection proc canEdit onMutated/>` — список поставок с позициями, doc-toggle, № УПД + pay status, «Отметить получение», «Расформировать»; модал «Создать поставку».

- [ ] **Шаг 1: implementation** — `frontend/src/components/support/DeliverySection.tsx`:
```tsx
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Modal } from '../Modal'
import { DocToggle } from './DocToggle'
import { PayChip } from './PayChip'
import { EmptyState } from '../EmptyState'
import {
  createDelivery,
  deleteDelivery,
  patchDelivery,
  upsertUpd,
  type DeliveryOut,
} from '../../api/support'
import { money } from '../../lib/format'
import type { ProcedureDetail } from '../../api/procedures'

const DOC_FIELDS: { field: 'doc_ttn' | 'doc_m15' | 'doc_upd' | 'doc_sert'; label: string }[] = [
  { field: 'doc_ttn', label: 'ТТН' },
  { field: 'doc_m15', label: 'М-15' },
  { field: 'doc_upd', label: 'УПД' },
  { field: 'doc_sert', label: 'Серт' },
]

function lastErrorMessage(err: unknown): string {
  const e = err as { body?: { detail?: string } } | null
  return e?.body?.detail ?? 'Ошибка'
}

export function DeliverySection({
  proc,
  canEditThis,
  refresh,
}: {
  proc: ProcedureDetail
  canEditThis: boolean
  refresh: () => Promise<void>
}) {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [err, setErr] = useState<string | null>(null)
  const [updDrafts, setUpdDrafts] = useState<Record<number, string>>({})

  const awaiting = proc.positions.filter((p) => p.delivery_id == null)
  const deliveries = [...proc.deliveries].sort((a, b) => a.n - b.n)

  async function run(fn: () => Promise<unknown>) {
    try {
      setErr(null)
      await fn()
      await refresh()
    } catch (e) {
      setErr(lastErrorMessage(e))
    }
  }

  const createMut = () =>
    run(async () => {
      if (selected.size === 0) return
      await createDelivery(proc.id, { positions: [...selected] })
      setCreateOpen(false)
      setSelected(new Set())
    })
  const toggleDoc = (d: DeliveryOut, field: 'doc_ttn' | 'doc_m15' | 'doc_upd' | 'doc_sert') =>
    run(() => patchDelivery(d.id, { [field]: d[field] ? 0 : 1 }))
  const markDone = (d: DeliveryOut) => run(() => patchDelivery(d.id, { status: 'done' }))
  const disband = (d: DeliveryOut) => run(() => deleteDelivery(d.id))
  const submitUpd = (d: DeliveryOut, value: string) =>
    run(async () => {
      if (!value.trim()) return
      await upsertUpd(d.id, { upd: value.trim() })
      setUpdDrafts((m) => { const n = { ...m }; delete n[d.id]; return n })
    })

  return (
    <div className="block reg" style={{ ['--bc' as any]: 'var(--supp)' }}>
      <div className="block-h">
        <span className="btitle">Поставки ({deliveries.length})</span>
        <span className="sp" style={{ flex: 1 }} />
        {canEditThis && (
          <button
            className="btn primary"
            disabled={awaiting.length === 0}
            onClick={() => { setSelected(new Set()); setCreateOpen(true) }}
            title={awaiting.length === 0 ? 'Нет позиций в ожидании' : 'Создать поставку'}
          >
            + Создать поставку
          </button>
        )}
        {err && <span style={{ color: 'var(--late)', fontSize: 12 }}>{err}</span>}
      </div>

      {deliveries.length === 0 ? (
        <div style={{ padding: 12 }}><EmptyState title="Поставок нет" hint="Создайте поставку из позиций «ожидают отгрузки»." /></div>
      ) : (
        deliveries.map((d) => {
          const dPositions = proc.positions.filter((p) => p.delivery_id === d.id)
          const updValue = updDrafts[d.id] ?? d.upd?.upd ?? ''
          const canDisband = canEditThis && d.status === 'transit' && !d.upd
          const canMarkDone = canEditThis && d.status === 'transit'
          return (
            <div key={d.id} style={{ borderTop: '1px solid var(--line)', padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <strong>Поставка №{d.n}</strong>
                <span className={`chip ${d.status === 'done' ? 'ok' : 'proc'} mini`}>
                  {d.status === 'done' ? 'Получена' : 'В пути'}
                </span>
                {d.date && <span style={{ color: 'var(--muted)', fontSize: 12 }}>от {d.date}</span>}
                {d.eta && d.status === 'transit' && <span style={{ color: 'var(--muted)', fontSize: 12 }}>ETA {d.eta}</span>}
                <span className="sp" style={{ flex: 1 }} />
                {canMarkDone && <button className="btn" onClick={() => markDone(d)}>Отметить получение</button>}
                {canDisband && <button className="btn" onClick={() => disband(d)}>Расформировать</button>}
              </div>

              <table className="postbl" style={{ marginBottom: 8 }}>
                <thead>
                  <tr><th>Наименование</th><th>Кол-во</th><th>Ед.</th><th>Сумма</th></tr>
                </thead>
                <tbody>
                  {dPositions.map((p) => (
                    <tr key={p.id}>
                      <td>{p.name}</td><td>{p.qty}</td><td>{p.unit ?? '—'}</td>
                      <td>{money(p.price != null ? Math.round(p.qty * p.price) : null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                {DOC_FIELDS.map((df) => (
                  <DocToggle
                    key={df.field}
                    label={df.label}
                    on={!!d[df.field]}
                    disabled={!canEditThis}
                    onClick={() => toggleDoc(d, df.field)}
                  />
                ))}
                <span style={{ flex: 1 }} />
                {canEditThis ? (
                  <>
                    <input
                      placeholder="№ УПД"
                      value={updValue}
                      onChange={(e) => setUpdDrafts((m) => ({ ...m, [d.id]: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') submitUpd(d, updValue) }}
                      style={{ border: '1px solid var(--line)', borderRadius: 5, padding: '3px 8px', fontFamily: 'inherit', fontSize: 12, width: 150 }}
                    />
                    <button className="btn" disabled={!updValue.trim() || updValue === (d.upd?.upd ?? '')} onClick={() => submitUpd(d, updValue)}>
                      Ввести УПД
                    </button>
                  </>
                ) : (
                  d.upd?.upd && <span style={{ fontSize: 12 }}>УПД: {d.upd.upd}</span>
                )}
                <PayChip payStatus={d.upd?.pay_status} />
              </div>
            </div>
          )
        })
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Создать поставку"
        width={620}
        footer={
          <>
            <button className="btn" onClick={() => setCreateOpen(false)}>Отмена</button>
            <button className="btn primary" disabled={selected.size === 0} onClick={createMut}>
              Создать ({selected.size})
            </button>
          </>
        }
      >
        {awaiting.length === 0 ? (
          <EmptyState title="Нет позиций в ожидании отгрузки" />
        ) : (
          <table className="postbl">
            <thead>
              <tr><th></th><th>Наименование</th><th>Кол-во</th><th>Ед.</th></tr>
            </thead>
            <tbody>
              {awaiting.map((p) => {
                const checked = selected.has(p.id)
                return (
                  <tr key={p.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setSelected((prev) => {
                            const n = new Set(prev)
                            if (checked) n.delete(p.id); else n.add(p.id)
                            return n
                          })
                        }
                      />
                    </td>
                    <td>{p.name}</td><td>{p.qty}</td><td>{p.unit ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Modal>
    </div>
  )
}
```
- [ ] **Шаг 2: wire into `SupportCard`** — в `frontend/src/cards/SupportCard.tsx`: добавить импорт `import { DeliverySection } from '../components/support/DeliverySection'` и вместо комментария `{/* Поставки — подключается в Task 6.3.5b (<DeliverySection/>) */}` вставить:
```tsx
      <DeliverySection proc={proc} canEditThis={canEditThis} refresh={refresh} />
```
- [ ] **Шаг 3: tsc.** `cd frontend && npx tsc --noEmit` → 0 errors.
- [ ] **Шаг 4: ui-checker (полный Б2 E2E).** Под админом: «Создать поставку» (выбрать ≥1 из ожидающих) → POST 200, поставка №1 `transit`, позиции ушли из «ожидают»; toggle ТТН/М-15/УПД/Серт (✕↔✓, PATCH 200); «Отметить получение» → `done` + дата (одностороннее; повторно — 409/disabled); «Расформировать» (transit, без УПД) → DELETE, позиции вернулись в «ожидают»; «Расформировать» после `done` или с УПД → disabled/409; ввод № УПД → POST `upd` 200, появляется `PayChip` «Ожидает оплаты» (сервер создал `upd_payment`); upsert (повторный ввод) → обновляет №. Под ролью без прав — все контролы read-only. Список `/soprovozhdenie` отражает изменения (доки-агрегат, прогресс, просрочка) после возврата.
- [ ] **Шаг 5: commit.**
```bash
git add frontend/src/components/support/DeliverySection.tsx frontend/src/cards/SupportCard.tsx
git commit -m "feat(support-fe): delivery section — create/docs/receive/disband + УПД (Phase 6.3.5b)"
```

---

## ⏸ СТОП — ПРОВЕРКА (Фаза 6.3 frontend)

- [ ] **Команды (главный агент):**
```bash
cd frontend && npx tsc --noEmit                 # 0 errors
cd frontend && npm test                         # ВЕСЬ набор PASS (0 регрессий; +новые тесты support/statusColors/supportView/buildQuery)
cd frontend && npm run build                    # production-сборка успешна (vite build)
```
- [ ] **ui-checker (полный сценарий, агент `ui-checker`):**
  - Вход под админом + форс-смена пароля; вкладка «В сопровождении» активна, счётчик — число; раскладка desktop ≥1280 (и 1440) без переполнения/скролл-багов; нет console errors/warnings, нет упавших сетевых (все `/support`, `/procedures/:id`, `/deliveries*`, `/dict/status_sdelki` 200).
  - **Список:** search (300ms debounce), sort-select (10 ключей), «Показать завершённые/отменённые» (include_archived); in-row правка `status_sdelki`/`status_postavki`/План/Факт сохраняется; read-only под ролью без прав; клик строки → карточка.
  - **Карточка Б2:** шапка (договор, ФИО договорника, сумма договора с Σ-позиций, статусы, Срок ДД/План/Факт) правится и сохраняется; sister-switcher per-block; позиции read-only.
  - **Поставки:** создать (≥1 из ожидающих), doc-toggle ✓↔✕, «Отметить получение» (one-way), «Расформировать» (transit + без УПД), № УПД → «Ожидает оплаты» (серверный `upd_payment`), upsert №.
  - **Регрессия Б1:** `Zakupka` (список + карточка, `StatusSelect` без `color` → дефолт `procStatusChip`) работает как прежде; «Передать в сопровождение» из закупки двигает процедуру в `/soprovozhdenie`.
  - Форматы ru-RU (money ₽, даты ДД.ММ.ГГ); ролевой гейтинг (Комплектация → 403 на PATCH/delivery/upd через UI — контролы скрыты/read-only).
- [ ] **git log:** коммиты 6.3.1 … 6.3.5b на `feat/phase-6`, linear.
- [ ] **Dev-окружение:** БД цела, uvicorn + vite поднимаются. Скриншоты ui-checker сохранены (как в прежних фазах).
- [ ] **Жду подтверждения пользователя перед PR/merge в main.**

---

## Self-Review (главный агент после написания)

- **Покрытие спеки:**
  - `12-page-v-soprovozhdenii.md` §2 макет (заголовок+счётчик, фильтры/сортировка/поиск, таблица) → 6.3.4 ✓; §3 таблица (все колонки, in-row правка сделки/поставки/План/Факт, клик→карточка, фильтры/сортировка/поиск, активные по умолчанию + архив) → 6.3.4 ✓; §4 что в карточке → 6.3.5a/b ✓; §5 действия → 6.3.5a (договор/статусы/даты) + 6.3.5b (поставка/получение/документы/УПД) ✓; §8 бизнес-правила (поставка не пустая, документы полный набор, просрочка производная, УПД→Оплаты) → бэкенд 6.2 + UI ✓; §9 решения (поставки в карточке; План=свободный ввод, Факт=ручной) → 6.3.5a ✓.
  - `16-card-zayavka.md` §4 Б2 (шапка+договор+сумма, статусы, Срок ДД/План/Факт, поставки per-delivery с документами-кнопками ✓↔✕, № УПД+статус оплаты, создать/расформировать transit/отметить получение, «ожидают отгрузки», УПД→Оплаты, комментарии/история) → 6.3.5a/b ✓; §5 переключатель сестёр → 6.3.5a `sisterRoute` ✓. Комментарии/«История» — placeholder EmptyState (Фаза 10, как в Б1) — отмечено.
  - `32-calculations.md` (derived поля) — считаются на бэкенде; фронт только рендерит (`OverduePct`/`Progress`/`DocsSquares`) → 6.3.3/6.3.4 ✓.
- **Плейсхолдеры:** нет TBD/«аналогично»; код приведён полностью для impl и тестов; пометки «копия дословно из Zakupka.tsx/ProcedureCard.tsx» относятся к устойчивым каноничным именам классов/хуков, подтверждённым картой кодовой базы (workflow map-frontend-for-phase63).
- **Согласованность типов:** `SupportListItem`/`DeliveryOut`/`UpdOut`/`DocsAggregate` определены в `api/support.ts`; `ProcedureDetail` widened (+Б2 +`deliveries: DeliveryOut[]`), `ProcedurePosition` +`delivery_id`, `ProcedurePatch` +Б2 — в `api/procedures.ts` и импортируют `DeliveryOut` из `./support`; `STATUS_POSTAVKI` — `as const` array, `StatusPostavki` = union; query-ключи `['support', ...]`/`['procedure', id]`/`['support', {tabCounter:true}]` едины; CSS-классы `.ovd`/`.w`/`.b`, `.docsq`/`span.no`, `.prog`/`.done`/`.bar i`/`.pn`, `.doctag`/`.no`, `.pchip`/`.await`/`.paid`/`.late` дословно из `zakupki-crm.css`; `StatusSelect.color` пробрасывает `sdelkiStatusChip`/`postavkiStatusChip`.
- **Регрессия:** `StatusSelect` — опциональный `color` с дефолтом `procStatusChip` (Zakupka не меняется); `procedures.ts` widen обратно совместим (Б2-поля nullable, `deliveries` default нет — но `getProcedure` всегда вернёт массив; `ProcedureDetail.deliveries` обязателен, бэкенд всегда отдаёт `[]`). ProcedureCard (Б1) нетронут.
- **Разложение/объём:** `SupportCard.tsx` (~6.3.5a) + `DeliverySection.tsx` (6.3.5b) — изоляция вместо одного ~700-строчного файла (решение пользователя). Чистая логика вынесена в `lib/supportView.ts` (тестируется); presentational-компоненты тонкие.
