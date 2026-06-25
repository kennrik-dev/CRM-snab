import { describe, it, expect } from 'vitest'
import { initials, roleLabel } from './CommandBar'
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
