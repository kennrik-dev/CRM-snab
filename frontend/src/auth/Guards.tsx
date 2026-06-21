import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

// For protected routes: requires authenticated (and not "must change password").
// Unauthenticated → /login. must_change_password → /change-password.
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return null
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  if (status === 'must_change_password' && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  return <>{children}</>
}

// For /change-password: allows both "must_change_password" and "authenticated".
// Unauthenticated → /login. Already-authenticated-no-pending → /.
export function RequireAuthOrChange({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  return <>{children}</>
}

export function RequireNoAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'authenticated') return <Navigate to="/" replace />
  return <>{children}</>
}

export function RequirePasswordChanged({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  if (status === 'must_change_password') return <Navigate to="/change-password" replace />
  return <>{children}</>
}