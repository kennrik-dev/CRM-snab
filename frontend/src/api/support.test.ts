import { describe, it, expect } from 'vitest'

// buildQuery не экспортируется наружу — тестируем через listSupport-подобную
// обёртку невозможно без мока fetch; поэтому экспортируем buildQuery ради теста.
import { buildQuery } from './support'

describe('buildQuery', () => {
  it('skips undefined / null / empty', () => {
    expect(buildQuery({ a: undefined, b: null, c: '', d: 0, e: false })).toBe('?d=0&e=false')
  })
  it('serializes strings/numbers/booleans', () => {
    // URLSearchParams percent-encodes non-ASCII (Т → %D0%A2); backend decodes back.
    expect(buildQuery({ search: 'Т-67', page: 2, include_archived: true })).toBe(
      '?search=%D0%A2-67&page=2&include_archived=true',
    )
  })
  it('returns empty string when nothing to send', () => {
    expect(buildQuery({})).toBe('')
    expect(buildQuery({ x: undefined })).toBe('')
  })
})
