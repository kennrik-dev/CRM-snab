import { describe, it, expect } from 'vitest'
import {
  overdueMod,
  progressState,
  sumPositionsKopecks,
  sisterRoute,
} from './supportView'

describe('overdueMod', () => {
  it('0 → green (base)', () => expect(overdueMod(0)).toBe(''))
  it('>0 and <50 → orange (w)', () => {
    expect(overdueMod(1)).toBe(' w')
    expect(overdueMod(49.9)).toBe(' w')
  })
  it('>=50 → red (b)', () => {
    expect(overdueMod(50)).toBe(' b')
    expect(overdueMod(100)).toBe(' b')
  })
  it('negative → green', () => expect(overdueMod(-5)).toBe(''))
})

describe('progressState', () => {
  it('zero total → 0%, not done', () => {
    expect(progressState(0, 0)).toEqual({ pct: 0, done: false })
  })
  it('none delivered → 0%', () => {
    expect(progressState(0, 3)).toEqual({ pct: 0, done: false })
  })
  it('partial → pct, not done', () => {
    const r = progressState(1, 3)
    expect(r.done).toBe(false)
    expect(Math.round(r.pct)).toBe(33)
  })
  it('all delivered → 100%, done', () => {
    expect(progressState(2, 2)).toEqual({ pct: 100, done: true })
  })
})

describe('sumPositionsKopecks', () => {
  it('sums qty*price (kopecks), price null → 0', () => {
    expect(
      sumPositionsKopecks([
        { qty: 2, price: 10000 },
        { qty: 1, price: null },
        { qty: 1.5, price: 5000 },
      ]),
    ).toBe(27500) // 2*100.00 + 0 + 1.5*50.00
  })
  it('empty → 0', () => expect(sumPositionsKopecks([])).toBe(0))
})

describe('sisterRoute', () => {
  it('soprovozhdenie → /soprovozhdenie/:id', () => {
    expect(sisterRoute('soprovozhdenie', 42)).toBe('/soprovozhdenie/42')
  })
  it('zakupka (or other) → /zakupka/:id', () => {
    expect(sisterRoute('zakupka', 7)).toBe('/zakupka/7')
    expect(sisterRoute(null, 7)).toBe('/zakupka/7')
  })
})
