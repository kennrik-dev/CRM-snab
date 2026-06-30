import { describe, it, expect } from 'vitest'
import { actorLabel } from './HistoryFeed'

describe('actorLabel', () => {
  it('passes a real name through', () => expect(actorLabel('Иванов')).toBe('Иванов'))
  it('null → Система', () => expect(actorLabel(null)).toBe('Система'))
  it('empty → Система', () => expect(actorLabel('')).toBe('Система'))
  it('whitespace → Система', () => expect(actorLabel('   ')).toBe('Система'))
})
