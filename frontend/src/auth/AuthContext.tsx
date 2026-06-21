import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { changePassword as apiChangePassword, login as apiLogin, logout as apiLogout, me as apiMe, type MeResponse, type User } from '../api/auth'
import type { PermMap } from '../lib/permissions'

export type AuthStatus =
  | 'loading'
  | 'authenticated'
  | 'unauthenticated'
  | 'must_change_password'

type AuthContextValue = {
  me: User | null
  permissions: PermMap | null
  status: AuthStatus
  login: (email: string, password: string, rememberMe: boolean) => Promise<void>
  logout: () => Promise<void>
  changePassword: (current: string, newPass: string) => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<User | null>(null)
  const [permissions, setPermissions] = useState<PermMap | null>(null)
  const [mustChange, setMustChange] = useState(false)
  const [status, setStatus] = useState<AuthStatus>('loading')

  const applyMe = useCallback((data: MeResponse) => {
    setMe(data.user)
    setPermissions(data.permissions)
    setMustChange(data.must_change_password)
    setStatus(data.must_change_password ? 'must_change_password' : 'authenticated')
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await apiMe()
      applyMe(data)
    } catch {
      setMe(null)
      setPermissions(null)
      setMustChange(false)
      setStatus('unauthenticated')
    }
  }, [applyMe])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const onLogout = () => {
      setMe(null)
      setPermissions(null)
      setMustChange(false)
      setStatus('unauthenticated')
    }
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean) => {
      const res = await apiLogin(email, password, rememberMe)
      if (res.must_change_password) {
        setMe(null)
        setPermissions(null)
        setMustChange(true)
        setStatus('must_change_password')
        return
      }
      await refresh()
    },
    [refresh],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setMe(null)
      setPermissions(null)
      setMustChange(false)
      setStatus('unauthenticated')
    }
  }, [])

  const changePassword = useCallback(
    async (current: string, newPass: string) => {
      await apiChangePassword(current, newPass)
      await refresh()
    },
    [refresh],
  )

  const value = useMemo<AuthContextValue>(
    () => ({ me, permissions, status, login, logout, changePassword, refresh }),
    [me, permissions, status, login, logout, changePassword, refresh],
  )

  // suppress unused-var for mustChange; kept on state for future UI hints
  void mustChange

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}