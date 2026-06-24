import { describe, it, expect } from 'vitest'
import { money, dateRu, num } from './format'

describe('money', () => {
  it('formats 0 as "0 ₽" (non-empty, contains ₽)', () => {
    const out = money(0)
    expect(out).not.toBe('')
    expect(out).toContain('₽')
  })

  it('formats 1234567 kopecks as 12 345,67 ₽ (kopecks → rubles, up to 2 decimals)', () => {
    const out = money(1234567)
    // 1 234 567 kopecks = 12 345.67 ₽. Kopecks preserved to 2 decimals.
    expect(out).toMatch(/12\s345,67/)
    expect(out).toContain('₽')
  })

  it('formats whole rubles without a decimal part (150000 kop → 1 500 ₽)', () => {
    const out = money(150000)
    expect(out).toMatch(/1\s500/)
    expect(out).not.toContain(',')
  })

  it('formats 150055 kopecks as 1 500,55 ₽ (kopecks shown)', () => {
    const out = money(150055)
    expect(out).toMatch(/1\s500,55/)
    expect(out).toContain('₽')
  })

  it('returns "—" for null', () => {
    expect(money(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(money(undefined)).toBe('—')
  })
})

describe('dateRu', () => {
  it('formats 2026-06-21 as 21.06.26', () => {
    expect(dateRu('2026-06-21')).toBe('21.06.26')
  })

  it('returns "—" for null', () => {
    expect(dateRu(null)).toBe('—')
  })

  it('returns "—" for empty string', () => {
    expect(dateRu('')).toBe('—')
  })

  it('returns "—" for garbage', () => {
    expect(dateRu('not-a-date')).toBe('—')
  })
})

describe('num', () => {
  it('formats 1234.5 with thousands sep and comma decimal', () => {
    const out = num(1234.5)
    expect(out).toContain('1')
    expect(out).toContain(',')
  })

  it('returns "—" for null', () => {
    expect(num(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(num(undefined)).toBe('—')
  })
})
