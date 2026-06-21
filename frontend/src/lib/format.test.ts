import { describe, it, expect } from 'vitest'
import { money, dateRu, num } from './format'

describe('money', () => {
  it('formats 0 as "0 ₽" (non-empty, contains ₽)', () => {
    const out = money(0)
    expect(out).not.toBe('')
    expect(out).toContain('₽')
  })

  it('formats 1 234 567 kopecks with thousands separator', () => {
    const out = money(1234567)
    expect(out).toMatch(/1[\s ]234[\s ]567/)
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
