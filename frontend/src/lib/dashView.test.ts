import { describe, it, expect } from 'vitest'
import { relTime, targetRoute, feedRoute } from './dashView'

const NOW = new Date('2026-06-27T12:00:00')

describe('relTime', () => {
  it('just now / minutes / hours', () => {
    expect(relTime('2026-06-27T11:59:30', NOW)).toBe('только что')
    expect(relTime('2026-06-27T11:55:00', NOW)).toBe('5 мин назад')
    expect(relTime('2026-06-27T10:00:00', NOW)).toBe('2 ч назад')
  })
  it('вчера / N дней', () => {
    expect(relTime('2026-06-26T10:00:00', NOW)).toBe('вчера')
    expect(relTime('2026-06-24T10:00:00', NOW)).toBe('3 дн назад')
  })
  it('older → DD.MM.YY', () => {
    expect(relTime('2026-05-20T10:00:00', NOW)).toBe('20.05.26')
  })
  it('unparseable / future → —', () => {
    expect(relTime('not-a-date', NOW)).toBe('—')
    expect(relTime('2026-06-28T10:00:00', NOW)).toBe('—')
  })
})

describe('targetRoute', () => {
  it('maps kinds to card routes', () => {
    expect(targetRoute({ kind: 'parent', id: 5 })).toBe('/komplektaciya/5')
    expect(targetRoute({ kind: 'procedure', id: 7 })).toBe('/soprovozhdenie/7')
    expect(targetRoute({ kind: 'payment', id: 9 })).toBe('/oplaty/9')
  })
  it('null/unknown → null', () => {
    expect(targetRoute(null)).toBeNull()
    expect(targetRoute({ kind: 'dict', id: 1 })).toBeNull()
  })
})

describe('feedRoute', () => {
  it('links parent & payment only', () => {
    expect(feedRoute({ kind: 'parent', id: 5 })).toBe('/komplektaciya/5')
    expect(feedRoute({ kind: 'payment', id: 9 })).toBe('/oplaty/9')
  })
  it('procedure → null (block unknown)', () => {
    expect(feedRoute({ kind: 'procedure', id: 7 })).toBeNull()
  })
})
