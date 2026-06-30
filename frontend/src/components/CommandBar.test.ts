import { describe, it, expect } from 'vitest'
import { initials, roleLabel, shouldSearch, procRoute } from './CommandBar'
import type { User } from '../api/auth'

function user(over: Partial<User> = {}): User {
  return {
    id: 1,
    email: 'admin@crm.local',
    full_name: 'Иванов И. И.',
    account_type: 'global',
    department: null,
    is_curator: false,
    global_role: 'Админ',
    is_active: true,
    ...over,
  }
}

describe('initials', () => {
  it('multi-word name → first + last initial, uppercased', () => {
    expect(initials('Иванов И. И.')).toBe('ИИ')
  })
  it('single word → first letter uppercased', () => {
    expect(initials('admin@crm.local')).toBe('A')
  })
  it('empty → dash', () => expect(initials('')).toBe('—'))
  it('whitespace-only → dash', () => expect(initials('   ')).toBe('—'))
})

describe('roleLabel', () => {
  it('global_role wins', () => expect(roleLabel(user({ global_role: 'Админ' }))).toBe('Админ'))
  it('global without role → Куратор', () =>
    expect(roleLabel(user({ global_role: null }))).toBe('Куратор'))
  it('department user → department', () =>
    expect(roleLabel(user({ account_type: 'department', department: 'Сопровождение', global_role: null }))).toBe('Сопровождение'))
  it('department curator → department · куратор', () =>
    expect(roleLabel(user({ account_type: 'department', department: 'Закупки', global_role: null, is_curator: true }))).toBe('Закупки · куратор'))
  it('department null → dash', () =>
    expect(roleLabel(user({ account_type: 'department', department: null, global_role: null }))).toBe('—'))
})

describe('shouldSearch', () => {
  it('true for ≥2 non-space chars', () => expect(shouldSearch('Т-67')).toBe(true))
  it('false for 1 char', () => expect(shouldSearch('Т')).toBe(false))
  it('false for empty', () => expect(shouldSearch('')).toBe(false))
  it('false for whitespace-only', () => expect(shouldSearch('   ')).toBe(false))
  it('true ignoring surrounding spaces', () => expect(shouldSearch('  аб  ')).toBe(true))
})

describe('procRoute', () => {
  it('zakupka block → /zakupka/:id', () => expect(procRoute('zakupka', 5)).toBe('/zakupka/5'))
  it('soprovozhdenie block → /soprovozhdenie/:id', () =>
    expect(procRoute('soprovozhdenie', 7)).toBe('/soprovozhdenie/7'))
  it('null block falls back to support card', () => expect(procRoute(null, 9)).toBe('/soprovozhdenie/9'))
})
