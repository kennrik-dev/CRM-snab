/**
 * Formatting helpers (ru-RU, Moscow TZ implied).
 * - money: input is integer KOPEEKS → "1 234 567 ₽" (NBSP thousands sep)
 * - dateRu: input is "YYYY-MM-DD" → "ДД.ММ.ГГ". Falls back to "—".
 * - num: input is number → thousands sep (NBSP) + comma decimal.
 */

const RUB_FORMAT = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
})

const NUM_FORMAT = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 2,
})

const PLACEHOLDER = '—'

export function money(kopecks: number | null | undefined): string {
  if (kopecks === null || kopecks === undefined) return PLACEHOLDER
  // Input is integer KOPEEKS — convert to rubles before formatting. Money is
  // stored as kopecks end-to-end (DB/API) and only converted to ₽ here, at
  // render. Round to whole rubles (the project displays money without kopecks
  // decimals). RUB_FORMAT adds the NBSP thousands separator + " ₽" suffix.
  return RUB_FORMAT.format(Math.round(kopecks / 100))
}

export function dateRu(iso: string | null | undefined): string {
  if (!iso) return PLACEHOLDER
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return PLACEHOLDER
  const [, y, mo, d] = m
  return `${d}.${mo}.${y.slice(2)}`
}

export function num(n: number | null | undefined): string {
  if (n === null || n === undefined) return PLACEHOLDER
  return NUM_FORMAT.format(n)
}
