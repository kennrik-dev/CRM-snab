import { apiFetch } from './client'

export type User = {
  id: number
  email: string
  full_name: string
  account_type: 'department' | 'global'
  department: string | null
  is_curator: boolean
  global_role: string | null
  is_active: boolean
}

export type MeResponse = {
  user: User
  permissions: string[]
  must_change_password: boolean
}

export type LoginResponse = {
  ok: boolean
  must_change_password: boolean
}

export function login(
  email: string,
  password: string,
  rememberMe: boolean,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: { email, password, remember_me: rememberMe },
  })
}

export function logout(): Promise<void> {
  return apiFetch<void>('/auth/logout', { method: 'POST' })
}

export function me(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me')
}

export function changePassword(current: string, newPass: string): Promise<void> {
  return apiFetch<void>('/auth/change-password', {
    method: 'POST',
    body: { current_password: current, new_password: newPass },
  })
}