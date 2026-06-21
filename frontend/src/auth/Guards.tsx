import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  if (status === 'must_change_password') return <Navigate to="/change-password" replace />
  return <>{children}</>
}

export function RequireNoAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'authenticated') return <Navigate to="/" replace />
  if (status === 'must_change_password') return <Navigate to="/change-password" replace />
  return <>{children}</>
}

export function RequirePasswordChanged({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return null
  if (status === 'must_change_password') return <Navigate to="/change-password" replace />
  if (status === 'unauthenticated') return <Navigate to="/login" replace />
  return <>{children}</>
}