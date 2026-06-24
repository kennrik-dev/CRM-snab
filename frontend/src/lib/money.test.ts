import { describe, expect, it } from 'vitest'
import { kopecksToRublesInput, rublesToKopecks } from './money'

describe('rublesToKopecks', () => {
  it('parses a whole-rubles string', () => {
    expect(rublesToKopecks('1500')).toBe(150000)
  })

  it('parses a dot-decimal string (one fractional digit)', () => {
    expect(rublesToKopecks('1500.5')).toBe(150050)
  })

  it('parses a dot-decimal string (two fractional digits)', () => {
    expect(rublesToKopecks('1500.55')).toBe(150055)
  })

  it('parses a comma-decimal string', () => {
    expect(rublesToKopecks('1500,55')).toBe(150055)
  })

  it('strips NBSP / space thousands separators', () => {
    expect(rublesToKopecks('1 500')).toBe(150000)
    expect(rublesToKopecks('1 500')).toBe(150000)
  })

  it('returns null for an empty string', () => {
    expect(rublesToKopecks('')).toBeNull()
  })

  it('returns null for null / undefined', () => {
    expect(rublesToKopecks(null)).toBeNull()
    expect(rublesToKopecks(undefined)).toBeNull()
  })

  it('returns null for non-numeric input', () => {
    expect(rublesToKopecks('abc')).toBeNull()
  })
})

describe('kopecksToRublesInput', () => {
  it('formats whole rubles without a decimal part', () => {
    expect(kopecksToRublesInput(150000)).toBe('1500')
  })

  it('formats a half-ruble with one decimal digit', () => {
    expect(kopecksToRublesInput(150050)).toBe('1500.5')
  })

  it('formats two decimal digits', () => {
    expect(kopecksToRublesInput(150055)).toBe('1500.55')
  })

  it('returns empty string for null / undefined', () => {
    expect(kopecksToRublesInput(null)).toBe('')
    expect(kopecksToRublesInput(undefined)).toBe('')
  })
})
