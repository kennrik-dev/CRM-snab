import { useAuth } from '../auth/AuthContext'
import type { User } from '../api/auth'

/** Avatar initials from a display name: first + last word initial (uppercased);
 * single word → its first letter; empty/whitespace → "—". Pure; unit-tested. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** Short role/department label for the header. Pure; unit-tested. */
export function roleLabel(me: User): string {
  if (me.global_role) return me.global_role
  if (me.account_type === 'global') return 'Куратор'
  const dept = me.department ?? '—'
  return me.is_curator ? `${dept} · куратор` : dept
}

export function CommandBar() {
  const { me, status } = useAuth()
  const authenticated = status === 'authenticated' && me != null
  const displayName = authenticated ? (me.full_name || me.email) : 'Гость'
  const sub = authenticated ? roleLabel(me) : 'не авторизован'

  return (
    <div className="cmd">
      <div className="mark">
        <div className="glyph"></div>
        СНАБ <small>единое окно</small>
      </div>
      <div className="search">
        <span className="mono">⌕</span>
        <input placeholder="заявка Т-67, № 1488, поставщик, УПД…" />
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
