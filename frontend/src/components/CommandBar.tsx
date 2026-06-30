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
