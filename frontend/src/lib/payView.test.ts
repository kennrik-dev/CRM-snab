import { describe, it, expect } from 'vitest'
import { buildPayBar } from './payView'

const BAR = { paid: 100000, await_: 200000, delivered_no_upd: 300000, contracted_no_delivery: 400000 }
// total = 1 000 000

describe('buildPayBar', () => {
  it('returns 4 segments in canon order with fractional widths that sum to 100', () => {
    const s = buildPayBar(BAR)
    expect(s.map((x) => x.cls)).toEqual(['sp-paid', 'sp-out', 'sp-del', 'sp-con'])
    expect(s.map((x) => x.value)).toEqual([100000, 200000, 300000, 400000])
    // widthPct is exact (fractional) so the bar always fills 100%.
    expect(s.reduce((a, x) => a + x.widthPct, 0)).toBeCloseTo(100, 5)
    expect(s[0].widthPct).toBeCloseTo(10, 5)
  })
  it('labelPct is the rounded percent for the segment text', () => {
    const s = buildPayBar(BAR)
    expect(s.map((x) => x.labelPct)).toEqual([10, 20, 30, 40])
  })
  it('a zero-valued segment still appears with 0 width/label', () => {
    const s = buildPayBar({ paid: 0, await_: 500000, delivered_no_upd: 0, contracted_no_delivery: 500000 })
    expect(s[0]).toMatchObject({ cls: 'sp-paid', value: 0, widthPct: 0, labelPct: 0 })
    expect(s[1].widthPct).toBeCloseTo(50, 5)
  })
  it('total 0 → all segments 0 (no divide-by-zero)', () => {
    const s = buildPayBar({ paid: 0, await_: 0, delivered_no_upd: 0, contracted_no_delivery: 0 })
    expect(s.every((x) => x.widthPct === 0 && x.labelPct === 0)).toBe(true)
  })
})
