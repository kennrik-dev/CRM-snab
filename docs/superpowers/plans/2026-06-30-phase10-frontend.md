# Phase 10 — Frontend Implementation Plan (search UI + comments + history + cards + regression)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the header `CommandBar` to live 5-group search; build `CommentFeed` + `HistoryFeed`; replace the «появится в Фазе 10» placeholders in `RequestCard`/`ProcedureCard` and add feeds to `SupportCard`/`PaymentCard`; reinforce format tests; run the final acceptance regression.

**Architecture:** Thin typed API clients mirror `api/reports.ts`/`api/support.ts` (`apiFetch`, `buildQuery`). Components follow the project's logic-only test discipline: **pure helpers are exported and unit-tested** (`*.test.ts`); rendering is verified by `tsc`/`vite build` + the `ui-checker` agent. React Query keys: `['comments',kind,id]`, `['history',kind,id]`, `['search',q]`. Mutations invalidate via `useQueryClient` (never await-refetch-then-reset).

**Tech Stack:** React 19, TypeScript, Vite, @tanstack/react-query, react-router-dom v7, vitest (logic-only — **no jsdom/RTL**).

## Global Constraints (copied verbatim from `docs/`)

- **Язык интерфейса** — русский (`ru-RU`).
- **Деньги/даты** — рендер через `lib/format` (`money` = копейки→`1 234 567 ₽`, `dateRu` = ISO→`ДД.ММ.ГГ`); относительное время — `relTime` (`lib/dashView`).
- **apiFetch** — единственная HTTP-обёртка: `/api${path}`, `credentials:'include'`; на 401 диспатчит `auth:logout`; бросает `{status,body}` на non-ok.
- **React Query defaults** — `retry:false`, `refetchOnWindowFocus:false`.
- **Команды:** `cd frontend && npm test` (vitest run), `npm run build` (`tsc -b && vite build`), `npm run lint`.
- **React-гочты (память crm-frontend-patterns):** StrictMode; `useMutation` `onSuccess` → `invalidateQueries` (НЕ await-refetch-then-reset); остерегаться `?? true` дефолтов; при отладке кэша предпочитать клиентскую навигацию, а не Playwright `goto`.

---

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/api/search.ts` | NEW: `SearchResult` (5 groups) + `getSearch` |
| `frontend/src/api/comments.ts` | NEW: `Comment`, `listComments`/`createComment`/`deleteComment` |
| `frontend/src/api/history.ts` | NEW: `AuditEntry`, `listHistory` |
| `frontend/src/components/CommandBar.tsx` | Live search: controlled input + debounce + dropdown + navigate; pure helpers `shouldSearch`, `procRoute` |
| `frontend/src/components/CommentFeed.tsx` | NEW: comments list + create + delete; pure `canDeleteComment`, `commentPlaceholder` |
| `frontend/src/components/HistoryFeed.tsx` | NEW: audit feed; pure `actorLabel` |
| `frontend/src/components/CommandBar.test.ts` | +`shouldSearch`, `procRoute` |
| `frontend/src/components/CommentFeed.test.ts` | NEW |
| `frontend/src/components/HistoryFeed.test.ts` | NEW |
| `frontend/src/cards/RequestCard.tsx` | Replace stub → `CommentFeed(parent)` |
| `frontend/src/cards/ProcedureCard.tsx` | Replace 2 stubs → `CommentFeed` + `HistoryFeed(procedure)` |
| `frontend/src/cards/SupportCard.tsx` | +`CommentFeed` + `HistoryFeed(procedure)` |
| `frontend/src/cards/PaymentCard.tsx` | +`HistoryFeed(upd_payment)` |
| `frontend/src/lib/format.test.ts` | +exact spec literals (`1 234 567 ₽`, `ДД.ММ.ГГ`, comma decimal) |

**Без нового CSS** (`.cmt*` уже в `styles/zakupki-crm.css`; «История» переиспользует `.fitem`/`.ft2`).

---

## Task F1: Typed API clients (search, comments, history)

**Files:**
- Create: `frontend/src/api/search.ts`, `frontend/src/api/comments.ts`, `frontend/src/api/history.ts`

**Interfaces:**
- Consumes: `apiFetch` (`./client`), `buildQuery` (`./support`). Backend contracts from Phase 10 backend plan (B1–B3).
- Produces: `getSearch(q, limit?)`, `listComments(kind,id,page?)`/`createComment(payload)`/`deleteComment(id)`, `listHistory(kind,id,page?)` + mirror types.

> These are thin typed wrappers (no logic) — their correctness gate is `tsc`/build plus the consuming components' tests (F2–F4). No separate unit test (consistent with `api/reports.ts` having none).

- [ ] **Step 1: Create `frontend/src/api/search.ts`:**

```ts
import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало GET /search (Phase 10 B1). 5 групп; procedures содержат block для роутинга.

export type SearchParent = { id: number; code: string; title: string }
export type SearchProcedure = {
  id: number
  proc: string | null
  supplier: string | null
  tender_id: number
  block: string
}
export type SearchSupplier = { id: number; name: string; proc_count: number }
export type SearchTender = { id: number; num: string; parent_id: number; parent_code: string }
export type SearchPayment = { id: number; upd: string; supplier: string | null }
export type SearchResult = {
  parents: SearchParent[]
  procedures: SearchProcedure[]
  suppliers: SearchSupplier[]
  tenders: SearchTender[]
  payments: SearchPayment[]
}

export function getSearch(q: string, limit?: number): Promise<SearchResult> {
  return apiFetch<SearchResult>(`/search${buildQuery({ q, limit })}`)
}
```

- [ ] **Step 2: Create `frontend/src/api/comments.ts`:**

```ts
import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало /comments (Phase 10 B2). snake_case wire-типы; money/dates — как на сервере.

export type CommentTargetKind = 'parent' | 'tender' | 'procedure'

export type Comment = {
  id: number
  target_kind: string
  target_id: number
  author_id: number | null
  author: string | null
  role: string | null
  text: string
  created_at: string
}
export type CommentList = { items: Comment[]; total: number }
export type CommentCreate = { target_kind: CommentTargetKind; target_id: number; text: string }

export function listComments(
  target_kind: string,
  target_id: number,
  page?: number,
): Promise<CommentList> {
  return apiFetch<CommentList>(`/comments${buildQuery({ target_kind, target_id, page })}`)
}

export function createComment(payload: CommentCreate): Promise<Comment> {
  return apiFetch<Comment>('/comments', { method: 'POST', body: payload })
}

export function deleteComment(id: number): Promise<void> {
  return apiFetch<void>(`/comments/${id}`, { method: 'DELETE' })
}
```

- [ ] **Step 3: Create `frontend/src/api/history.ts`:**

```ts
import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало GET /history (Phase 10 B3). actor = User.full_name | 'Система' (BE).

export type AuditEntry = { id: number; action: string; actor: string; created_at: string }
export type HistoryList = { items: AuditEntry[]; total: number }

export function listHistory(
  entity_kind: string,
  entity_id: number,
  page?: number,
): Promise<HistoryList> {
  return apiFetch<HistoryList>(`/history${buildQuery({ entity_kind, entity_id, page })}`)
}
```

- [ ] **Step 4: Verify it type-checks**

Run: `cd frontend && npx tsc -b --pretty false`
Expected: PASS (no type errors). (If the FE imports `SearchResult` etc. only later in F2–F4, unused-export is fine; `tsc` passes.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/search.ts frontend/src/api/comments.ts frontend/src/api/history.ts
git commit -m "feat(api): typed clients search/comments/history (Phase 10 F1)"
```

---

## Task F2: CommandBar live search (debounced dropdown)

**Files:**
- Modify: `frontend/src/components/CommandBar.tsx`
- Test: `frontend/src/components/CommandBar.test.ts`

**Interfaces:**
- Consumes: `getSearch` + `SearchResult` (F1); `useNavigate` (react-router-dom); `useQuery` (react-query); `useAuth`.
- Produces: pure helpers `shouldSearch(q): boolean` (≥2 non-space chars), `procRoute(block, id): string` (zakupka→`/zakupka/:id` else `/soprovozhdenie/:id`). Existing exports `initials`, `roleLabel` unchanged.

- [ ] **Step 1: Write the failing tests** — append to `frontend/src/components/CommandBar.test.ts`:

```ts
import { shouldSearch, procRoute } from './CommandBar'

describe('shouldSearch', () => {
  it('true for ≥2 non-space chars', () => expect(shouldSearch('Т-67')).toBe(true))
  it('false for 1 char', () => expect(shouldSearch('Т')).toBe(false))
  it('false for empty', () => expect(shouldSearch('')).toBe(false))
  it('false for whitespace-only', () => expect(shouldSearch('   ')).toBe(false))
  it('true ignoring surrounding spaces', () => expect(shouldSearch('  аб  ')).toBe(true))
})

describe('procRoute', () => {
  it('zakupka block → /zakupka/:id', () => expect(procRoute('zakupka', 5)).toBe('/zakupka/5'))
  it('soprovozhdenie block → /soprovozhdenie/:id', () =>
    expect(procRoute('soprovozhdenie', 7)).toBe('/soprovozhdenie/7'))
  it('null block falls back to support card', () => expect(procRoute(null, 9)).toBe('/soprovozhdenie/9'))
})
```

Update the import line at the top of the file from `import { initials, roleLabel } from './CommandBar'` to also import the new helpers (or add a second import line).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/CommandBar.test.ts`
Expected: FAIL — `shouldSearch`/`procRoute` not exported.

- [ ] **Step 3: Implement** — replace `frontend/src/components/CommandBar.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { getSearch, type SearchResult } from '../api/search'
import type { User } from '../api/auth'

/** Avatar initials from a display name. Pure; unit-tested. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** Short role/department label. Pure; unit-tested. */
export function roleLabel(me: User): string {
  if (me.global_role) return me.global_role
  if (me.account_type === 'global') return 'Куратор'
  const dept = me.department ?? '—'
  return me.is_curator ? `${dept} · куратор` : dept
}

/** Min trimmed length before firing a search (avoid 1-char noise). Pure; unit-tested. */
export function shouldSearch(q: string): boolean {
  return q.trim().length >= 2
}

/** Procedure route depends on block (zakupka card vs support card). Pure; unit-tested. */
export function procRoute(block: string | null | undefined, id: number): string {
  return block === 'zakupka' ? `/zakupka/${id}` : `/soprovozhdenie/${id}`
}

function SearchDropdown({
  results,
  onPick,
}: {
  results: SearchResult
  onPick: (route: string) => void
}) {
  const Group = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="sg">
      <div className="sg-h">{title}</div>
      {children}
    </div>
  )
  const Row = ({ label, sub, route }: { label: string; sub?: string; route: string | null }) => (
    <button
      type="button"
      className="sg-i"
      disabled={!route}
      style={route ? undefined : { cursor: 'default', color: 'var(--faint)' }}
      onClick={route ? () => onPick(route) : undefined}
    >
      <span>{label}</span>
      {sub && <span className="sg-s">{sub}</span>}
    </button>
  )
  const empty =
    results.parents.length + results.procedures.length + results.suppliers.length +
      results.tenders.length + results.payments.length ===
    0
  if (empty) return <div className="sg-empty">Ничего не найдено</div>
  return (
    <div className="sg-wrap">
      {results.parents.map((p) => (
        <Row key={`p${p.id}`} label={p.code} sub={p.title} route={`/komplektaciya/${p.id}`} />
      ))}
      {results.procedures.map((p) => (
        <Row key={`pr${p.id}`} label={p.proc ?? `#${p.id}`} sub={p.supplier ?? undefined} route={procRoute(p.block, p.id)} />
      ))}
      {results.tenders.map((t) => (
        <Row key={`t${t.id}`} label={t.num} sub={t.parent_code} route={`/komplektaciya/${t.parent_id}`} />
      ))}
      {results.payments.map((pm) => (
        <Row key={`pm${pm.id}`} label={pm.upd} sub={pm.supplier ?? undefined} route={`/oplaty/${pm.id}`} />
      ))}
      {results.suppliers.map((s) => (
        <Row key={`s${s.id}`} label={s.name} sub={`${s.proc_count} процедур`} route={null} />
      ))}
    </div>
  )
}

export function CommandBar() {
  const { me, status } = useAuth()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')

  // debounce 300ms
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300)
    return () => clearTimeout(t)
  }, [q])

  const searchQ = useQuery({
    queryKey: ['search', debounced],
    queryFn: () => getSearch(debounced),
    enabled: shouldSearch(debounced),
  })

  const results = shouldSearch(debounced) ? searchQ.data : undefined
  const authenticated = status === 'authenticated' && me != null
  const displayName = authenticated ? me.full_name || me.email : 'Гость'
  const sub = authenticated ? roleLabel(me) : 'не авторизован'

  const pick = (route: string) => {
    navigate(route)
    setQ('')
    setDebounced('')
  }

  return (
    <div className="cmd">
      <div className="mark">
        <div className="glyph"></div>
        СНАБ <small>единое окно</small>
      </div>
      <div className="search">
        <span className="mono">⌕</span>
        <input
          placeholder="заявка Т-67, № 1488, поставщик, УПД…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setQ('')
              setDebounced('')
            }
          }}
        />
        {results && <SearchDropdown results={results} onPick={pick} />}
      </div>
      <div className="spacer"></div>
      <div className="who" title={authenticated ? me.email : undefined}>
        <div className="av">{authenticated ? initials(me.full_name || me.email) : '—'}</div>
        <div className="nm">
          <b>{displayName}</b>
          <span>{sub}</span>
        </div>
      </div>
    </div>
  )
}
```

> `.sg*` dropdown classes are not in the canon stylesheet. Add minimal styles for them in a follow-up style tweak OR accept unstyled-but-functional (ui-checker will flag). If the canon `.search` already provides a positioned container, keep the dropdown simple. This is a Phase-10 UX addition with no canon; keep it visually consistent with existing `.cmd` tokens (background `#23272c`, mono font).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/CommandBar.test.ts`
Expected: PASS (initials, roleLabel, shouldSearch, procRoute).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CommandBar.tsx frontend/src/components/CommandBar.test.ts
git commit -m "feat(search): live debounced CommandBar dropdown — 5 groups, navigate on pick (Phase 10 F2)"
```

---

## Task F3: CommentFeed component (list + create + delete)

**Files:**
- Create: `frontend/src/components/CommentFeed.tsx`
- Test: `frontend/src/components/CommentFeed.test.ts`

**Interfaces:**
- Consumes: `listComments`/`createComment`/`deleteComment` (F1); `useAuth`; `relTime` (`lib/dashView`); `initials`/`roleLabel` (CommandBar).
- Produces: `<CommentFeed targetKind targetId />`; pure `canDeleteComment(me, comment)`, `commentPlaceholder(role)`.

- [ ] **Step 1: Write the failing tests** — create `frontend/src/components/CommentFeed.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { canDeleteComment, commentPlaceholder } from './CommentFeed'
import type { Comment } from '../api/comments'

function c(over: Partial<Comment> = {}): Comment {
  return {
    id: 1,
    target_kind: 'parent',
    target_id: 1,
    author_id: 7,
    author: 'Иванов',
    role: 'Закупки',
    text: 'x',
    created_at: '2026-06-30 10:00:00',
    ...over,
  }
}

describe('canDeleteComment', () => {
  it('author can delete own', () =>
    expect(canDeleteComment({ id: 7, global_role: null }, c())).toBe(true))
  it('non-author non-admin cannot', () =>
    expect(canDeleteComment({ id: 8, global_role: null }, c())).toBe(false))
  it('admin can delete any', () =>
    expect(canDeleteComment({ id: 99, global_role: 'Админ' }, c())).toBe(true))
  it('null user cannot', () => expect(canDeleteComment(null, c())).toBe(false))
  it('comment with null author_id: only admin', () => {
    expect(canDeleteComment({ id: 7, global_role: null }, c({ author_id: null }))).toBe(false)
    expect(canDeleteComment({ id: 7, global_role: 'Админ' }, c({ author_id: null }))).toBe(true)
  })
})

describe('commentPlaceholder', () => {
  it('stamps the role', () => expect(commentPlaceholder('Закупки')).toContain('Закупки'))
  it('falls back to dash for null', () => expect(commentPlaceholder(null)).toContain('—'))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/CommentFeed.test.ts`
Expected: FAIL — module not found / helpers not exported.

- [ ] **Step 3: Implement** — create `frontend/src/components/CommentFeed.tsx`:

```tsx
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listComments, createComment, deleteComment, type Comment, type CommentTargetKind } from '../api/comments'
import { useAuth } from '../auth/AuthContext'
import { relTime } from '../lib/dashView'
import { initials, roleLabel } from './CommandBar'

type Me = { id: number; global_role: string | null; full_name: string } | null

/** Delete allowed for the author OR Админ. Pure; unit-tested. */
export function canDeleteComment(me: Me, c: Comment): boolean {
  if (!me) return false
  return c.author_id === me.id || me.global_role === 'Админ'
}

/** Role-stamped input placeholder (canon). Pure; unit-tested. */
export function commentPlaceholder(role: string | null): string {
  return `Комментарий по заявке от лица «${role ?? '—'}»…`
}

export function CommentFeed({
  targetKind,
  targetId,
}: {
  targetKind: CommentTargetKind
  targetId: number
}) {
  const qc = useQueryClient()
  const { me } = useAuth()
  const [text, setText] = useState('')
  const enabled = Number.isFinite(targetId) && targetId > 0

  const q = useQuery({
    queryKey: ['comments', targetKind, targetId],
    queryFn: () => listComments(targetKind, targetId),
    enabled,
  })

  const addMut = useMutation({
    mutationFn: (t: string) =>
      createComment({ target_kind: targetKind, target_id: targetId, text: t }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments', targetKind, targetId] })
      setText('')
    },
  })

  const delMut = useMutation({
    mutationFn: (id: number) => deleteComment(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments', targetKind, targetId] }),
  })

  const items = q.data?.items ?? []
  const submit = () => {
    const t = text.trim()
    if (t && !addMut.isPending) addMut.mutate(t)
  }

  return (
    <div className="comments">
      {items.length === 0 ? (
        <div className="cmt-empty">Пока нет комментариев. Будьте первым.</div>
      ) : (
        items.map((cm) => (
          <div className="cmt" key={cm.id}>
            <div className={`cmt-av${cm.author_id === me?.id ? ' me' : ''}`}>
              {initials(cm.author ?? '?')}
            </div>
            <div className="cmt-b">
              <div className="cmt-h">
                <b>{cm.author ?? '—'}</b>
                {cm.role && <span className="cmt-r">{cm.role}</span>}
                <span className="cmt-t">{relTime(cm.created_at)}</span>
              </div>
              <div className="cmt-x">{cm.text}</div>
            </div>
            {canDeleteComment(me, cm) && (
              <button
                type="button"
                title="Удалить комментарий"
                onClick={() => delMut.mutate(cm.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--faint)',
                  cursor: 'pointer',
                  fontSize: 16,
                  padding: '0 4px',
                }}
              >
                ×
              </button>
            )}
          </div>
        ))
      )}
      <div className="cmt-new">
        <div className="cmt-av me">{me ? initials(me.full_name) : '—'}</div>
        <textarea
          placeholder={commentPlaceholder(me ? roleLabel(me) : null)}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit()
          }}
          rows={2}
        />
        <button
          type="button"
          className="btn primary"
          disabled={!text.trim() || addMut.isPending}
          onClick={submit}
        >
          {addMut.isPending ? 'Отправка…' : 'Отправить'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/CommentFeed.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CommentFeed.tsx frontend/src/components/CommentFeed.test.ts
git commit -m "feat(comments): CommentFeed — list/create/delete, author|admin gating (Phase 10 F3)"
```

---

## Task F4: HistoryFeed component

**Files:**
- Create: `frontend/src/components/HistoryFeed.tsx`
- Test: `frontend/src/components/HistoryFeed.test.ts`

**Interfaces:**
- Consumes: `listHistory` (F1); `relTime` (`lib/dashView`).
- Produces: `<HistoryFeed entityKind entityId />`; pure `actorLabel(actor)`.

- [ ] **Step 1: Write the failing tests** — create `frontend/src/components/HistoryFeed.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { actorLabel } from './HistoryFeed'

describe('actorLabel', () => {
  it('passes a real name through', () => expect(actorLabel('Иванов')).toBe('Иванов'))
  it('null → Система', () => expect(actorLabel(null)).toBe('Система'))
  it('empty → Система', () => expect(actorLabel('')).toBe('Система'))
  it('whitespace → Система', () => expect(actorLabel('   ')).toBe('Система'))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/HistoryFeed.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** — create `frontend/src/components/HistoryFeed.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { listHistory } from '../api/history'
import { relTime } from '../lib/dashView'

/** Actor fallback for a null/blank audit actor. Pure; unit-tested. (BE already sends 'Система'.) */
export function actorLabel(actor: string | null | undefined): string {
  return actor && actor.trim() ? actor : 'Система'
}

export function HistoryFeed({
  entityKind,
  entityId,
}: {
  entityKind: string
  entityId: number
}) {
  const q = useQuery({
    queryKey: ['history', entityKind, entityId],
    queryFn: () => listHistory(entityKind, entityId),
    enabled: Number.isFinite(entityId) && entityId > 0,
  })
  const items = q.data?.items ?? []
  return (
    <div className="history" style={{ maxHeight: 240, overflowY: 'auto' }}>
      {items.length === 0 ? (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          Журнал действий пуст.
        </div>
      ) : (
        items.map((e) => (
          <div className="fitem" key={e.id}>
            <span className="ft2">{relTime(e.created_at)}</span>
            <div>
              <b>{actorLabel(e.actor)}</b> <span>{e.action}</span>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/HistoryFeed.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/HistoryFeed.tsx frontend/src/components/HistoryFeed.test.ts
git commit -m "feat(history): HistoryFeed — newest-first audit feed reusing .fitem + relTime (Phase 10 F4)"
```

---

## Task F5: Wire feeds into the 4 cards

**Files:**
- Modify: `frontend/src/cards/RequestCard.tsx` (replace stub → CommentFeed)
- Modify: `frontend/src/cards/ProcedureCard.tsx` (replace 2 stubs)
- Modify: `frontend/src/cards/SupportCard.tsx` (add CommentFeed + HistoryFeed)
- Modify: `frontend/src/cards/PaymentCard.tsx` (add HistoryFeed)

**Interfaces:**
- Consumes: `CommentFeed` (F3), `HistoryFeed` (F4). Card data: `RequestCard`→`req.id`; `ProcedureCard`/`SupportCard`→`proc.id`; `PaymentCard`→`paymentId`.

> No unit test (pure wiring); gate is `tsc` + `vite build` + ui-checker.

- [ ] **Step 1: RequestCard** — add import near the other imports:

```tsx
import { CommentFeed } from '../components/CommentFeed'
```

Replace the comments stub block (`RequestCard.tsx:484-487`):

```tsx
          <EmptyState
            title="Комментариев пока нет"
            hint="Лента комментариев появится в Фазе 10."
          />
```

with:

```tsx
          <CommentFeed targetKind="parent" targetId={req.id} />
```

(Confirm the parent object variable is `req` — it is, per `req.positions` at line 460.)

- [ ] **Step 2: ProcedureCard** — add imports:

```tsx
import { CommentFeed } from '../components/CommentFeed'
import { HistoryFeed } from '../components/HistoryFeed'
```

Replace the comments stub (`ProcedureCard.tsx:741-744`):

```tsx
          <EmptyState
            title="Комментариев пока нет"
            hint="Лента комментариев появится в Фазе 10."
          />
```

with:

```tsx
          <CommentFeed targetKind="procedure" targetId={proc.id} />
```

Replace the history stub (`ProcedureCard.tsx:760`):

```tsx
          <EmptyState title="Пусто" hint="Журнал действий появится в Фазе 10." />
```

with:

```tsx
          <HistoryFeed entityKind="procedure" entityId={proc.id} />
```

(Confirm `proc` — yes, `proc.positions`/`proc.id` are used in this card. If `EmptyState` becomes unused after these edits, leave its import — other cards still use it; do not remove.)

- [ ] **Step 3: SupportCard** — add imports (same two as ProcedureCard) and append the two feeds at the end of the returned tree, right before the closing `</div>` of the `.wrap` (after `<DeliverySection ... />`):

```tsx
      <DeliverySection proc={proc} canEditThis={canEditThis} refresh={refresh} />

      <div className="block reg" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
        <div className="block-h"><span className="btitle">Комментарии</span></div>
        <div style={{ padding: 12 }}>
          <CommentFeed targetKind="procedure" targetId={proc.id} />
        </div>
      </div>

      <div className="block reg" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
        <div className="block-h"><span className="btitle">История</span></div>
        <div style={{ padding: 12 }}>
          <HistoryFeed entityKind="procedure" entityId={proc.id} />
        </div>
      </div>
    </div>
  )
}
```

(`CSSProperties` is already imported in SupportCard; `proc.id` is used elsewhere in the card.)

- [ ] **Step 4: PaymentCard** — add import and insert a История block after the positions table `</div>` (the `.pcd-body` close, ~line 301) and before the closing `</div>` of `.pcd`:

```tsx
import { HistoryFeed } from '../components/HistoryFeed'
```

Insert before the `.pcd` closing `</div>` (after `.pcd-body`):

```tsx
        <div style={{ padding: '0 22px 22px' }}>
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
            История
          </div>
          <HistoryFeed entityKind="upd_payment" entityId={paymentId} />
        </div>
```

- [ ] **Step 5: Verify type-check + build + ui-checker**

Run: `cd frontend && npx tsc -b --pretty false && npm run build`
Expected: PASS (no type errors; build succeeds).

Dispatch `ui-checker` (`.claude/agents/ui-checker.md`): open each card (RequestCard `/komplektaciya/:id`, ProcedureCard `/zakupka/:id`, SupportCard `/soprovozhdenie/:id`, PaymentCard `/oplaty/:id`), confirm CommentFeed/HistoryFeed render (comments list + input; history rows or empty text), and the CommandBar dropdown shows grouped results and navigates on click. Console/network clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/cards/RequestCard.tsx frontend/src/cards/ProcedureCard.tsx frontend/src/cards/SupportCard.tsx frontend/src/cards/PaymentCard.tsx
git commit -m "feat(cards): wire CommentFeed/HistoryFeed into Request/Procedure/Support/Payment cards (Phase 10 F5)"
```

---

## Task F6: Reinforce format tests with exact spec literals

**Files:**
- Modify: `frontend/src/lib/format.test.ts`

**Interfaces:** none (test-only).

- [ ] **Step 1: Write the failing tests** — append to `frontend/src/lib/format.test.ts`:

```ts
// Exact spec literals (docs/33 §1): "1 234 567 ₽", ДД.ММ.ГГ, comma decimal.
describe('spec literals (Phase 10 F6)', () => {
  it('money: 123456700 kop → "1 234 567 ₽" (NBSP thousands, no decimals)', () => {
    const out = money(123456700) // = 1 234 567.00 ₽
    expect(out).toMatch(/1\s234\s567/)
    expect(out).toContain('₽')
    expect(out).not.toContain(',')
  })

  it('dateRu: "2026-06-30" → "30.06.26" (ДД.ММ.ГГ)', () => {
    expect(dateRu('2026-06-30')).toBe('30.06.26')
  })

  it('num: 1234567.89 → "1 234 567,89" (NBSP thousands, comma decimal)', () => {
    expect(num(1234567.89)).toMatch(/1\s234\s567,89/)
  })
})
```

- [ ] **Step 2: Run tests to verify they pass** (these assert existing conformant behavior, so they pass immediately — they lock the spec literals against regressions):

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: PASS. (If any fails, `lib/format.ts` regressed — fix the formatter, not the test.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/format.test.ts
git commit -m "test(format): lock spec literals — 1 234 567 ₽ / ДД.ММ.ГГ / comma decimal (Phase 10 F6)"
```

---

## Task F7: Final regression (10.4) — acceptance gate

**Files:** none (verification + the `docs/40-acceptance.md` §6 checklist).

- [ ] **Step 1: Full automated suites green**

Run:
- `cd backend && "$PY" -m pytest -q` → all PASS (incl. Phase 10 B1–B5).
- `cd frontend && npm test` → all vitest PASS.
- `cd frontend && npm run build` → `tsc -b && vite build` succeeds, 0 errors.
- `cd frontend && npm run lint` → no errors.

- [ ] **Step 2: Full ui-checker regression** — dispatch the `ui-checker` agent (`.claude/agents/ui-checker.md`): прогнать все ключевые экраны на 1280 и 1440 — Дашборд, 4 рабочих страницы (Комплектация, В закупке, В сопровождении, Оплаты), 4 карточки (Request/Procedure/Support/Payment), Отчёты, логин — сверка с `Concept design/index.html`; сценарии приёмки `docs/40-acceptance.md` §6 (создание заявки с Excel-вставкой, «Взять в работу», дробление по поставщикам, смена статусов, «Передать в сопровождение», частичные поставки и документы, ввод № УПД, «Провести оплату», глобальный поиск, «История», комментарии); консоль и сеть чистые. Итог PASS/FAIL.

- [ ] **Step 3: 8-point acceptance checklist (`docs/40-acceptance.md` §6)** — confirm each:
  1. Маршрут заявки сквозь все блоки (each step by a role with the right).
  2. Иерархия (1 Т-67 → ≥1 торг → ≥1 процедура; независимость).
  3. Статусы блочной модели; просрочка вычисляется; «Закрыта» нет.
  4. Права (отдел / Куратор / Руководитель / Админ).
  5. Деньги (копейки↔₽ с НДС).
  6. Excel-вставка.
  7. Оплаты (все УПД; полная оплата).
  8. Расчёты по `docs/32`.

- [ ] **Step 4: Tag the phase complete** (no new code; this is the gate). If a migration were needed (it is not), run `alembic upgrade head` — the B5 hook backs up `crm.db` first.

---

## ⏸ СТОП — ПРОВЕРКА (Фаза 10, финальная)

- Команды: `pytest -q` PASS · `npm test` PASS · `npm run build` OK · `npm run lint` OK · ui-checker PASS.
- Человек: пройти **полный маршрут** одной заявки от создания `Т-67` до оплаты всех УПД под соответствующими ролями; проверить живой глобальный поиск (5 групп, переходы), «Историю» и комментарии в карточках; сверить с чек-листом `docs/40-acceptance.md` §6.
- **Жду подтверждения — это завершение проекта.** После — `superpowers:finishing-a-development-branch` (merge `feat/phase-10` → `main`).

---

## Self-Review (заполняется автором плана)

- **Spec coverage:** R2 search FE → F1(search.ts)+F2(CommandBar) ✓; R5 comments ordering/empty/placeholder → F3 ✓; R6 delete gating → F3 `canDeleteComment` ✓; R10 debounced dropdown → F2 ✓; R11 card wiring (4 cards) → F5 ✓; R12 История `.fitem` → F4 ✓; R14 format literals → F6 ✓; 10.4 regression → F7 ✓.
- **Placeholder scan:** нет TBD; весь код приведён дословно.
- **Type consistency:** `Comment`/`CommentList`/`CommentTargetKind` (F1 comments.ts) потребляются в F3; `SearchResult`/`SearchProcedure.block` (F1 search.ts) потребляются в F2 (`procRoute(p.block, p.id)`); `AuditEntry` (F1 history.ts) в F4. Бэкенд-контракты (B-план) и FE-типы зеркальны (snake_case, `block:string`, `actor:string`).
- **Test discipline:** FE-тесты — только чистые функции (нет jsdom/RTL в проекте); рендеринг проверяется `tsc`/build + ui-checker. F1 (тонкие клиенты) без unit-теста — верифицируются через `tsc` и потребителей (честно отмечено).
