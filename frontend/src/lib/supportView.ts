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
