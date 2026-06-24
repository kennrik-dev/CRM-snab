/**
 * Money conversion helpers for editable money fields.
 *
 * The backend stores money as INTEGER kopecks; users edit a rubles string.
 * These pure functions bridge the two without grouping separators so the
 * value round-trips cleanly through an <input>.
 *
 * - rublesToKopecks: user text (',' or '.' decimal, optional NBSP/space
 *   thousands) → integer kopecks. '' / null / undefined / NaN → null.
 * - kopecksToRublesInput: integer kopecks → editable rubles string ('.'
 *   decimal, no grouping, max 2 decimals). null/undefined → ''.
 */

export function rublesToKopecks(s: string | null | undefined): number | null {
  if (s === null || s === undefined) return null
  const trimmed = s.trim()
  if (trimmed === '') return null
  // Accept comma as a decimal separator and strip NBSP / regular-space
  // thousands separators so pasted canonical values parse too.
  const normalized = trimmed.replace(/[ \s]/g, '').replace(',', '.')
  const n = Number(normalized)
  if (!Number.isFinite(n)) return null
  return Math.round(n * 100)
}

export function kopecksToRublesInput(
  kop: number | null | undefined,
): string {
  if (kop === null || kop === undefined) return ''
  return (Math.round((kop / 100) * 100) / 100).toString()
}
