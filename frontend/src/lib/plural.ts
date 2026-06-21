/**
 * Russian noun pluralization for "заявка / заявки / заявок".
 *
 * The rule:
 *   - ends in 1 (and not 11) → singular ("заявка")
 *   - ends in 2..4 (and not 12..14) → few ("заявки")
 *   - everything else (0, 5..20, 22..24 endings, 11..14) → many ("заявок")
 */
export function pluralRequests(n: number): 'заявка' | 'заявки' | 'заявок' {
  const abs = Math.abs(n)
  const mod100 = abs % 100
  const mod10 = abs % 10
  if (mod100 >= 11 && mod100 <= 14) return 'заявок'
  if (mod10 === 1) return 'заявка'
  if (mod10 >= 2 && mod10 <= 4) return 'заявки'
  return 'заявок'
}
