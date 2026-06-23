import { describe, it, expect } from 'vitest'
import { sumPositionsKopecks } from './ProcedureCard'

// sumPositionsKopecks: Σ qty*price (price is INTEGER kopecks, nullable).
// Null/missing price contributes 0 to the sum.
describe('sumPositionsKopecks', () => {
  it('sums qty*price across mixed rows (null price → 0)', () => {
    const rows = [
      { qty: 2, price: 100 },
      { qty: 1, price: null },
      { qty: 0.5, price: 200 },
    ]
    // 2*100 + 0 + 0.5*200 = 200 + 0 + 100 = 300
    expect(sumPositionsKopecks(rows)).toBe(300)
  })

  it('returns 0 for an empty list', () => {
    expect(sumPositionsKopecks([])).toBe(0)
  })

  it('returns 0 when every price is null', () => {
    expect(
      sumPositionsKopecks([
        { qty: 5, price: null },
        { qty: 10, price: null },
      ]),
    ).toBe(0)
  })

  it('treats a zero qty row as contributing nothing', () => {
    expect(
      sumPositionsKopecks([
        { qty: 0, price: 999 },
        { qty: 3, price: 100 },
      ]),
    ).toBe(300)
  })
})
