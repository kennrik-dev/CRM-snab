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
