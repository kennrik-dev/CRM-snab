import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import type { ApiError } from '../api/client'

export function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password, rememberMe)
      navigate('/', { replace: true })
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr?.status === 401) {
        setError('Неверный email или пароль')
      } else {
        setError('Ошибка входа. Попробуйте позже.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-head">
          <div className="login-mark">СНАБ</div>
          <h1>Вход</h1>
        </div>

        <label className="login-field">
          <span>Email</span>
          <input
            type="email"
            className="rep-sel"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>

        <label className="login-field">
          <span>Пароль</span>
          <input
            type="password"
            className="rep-sel"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        <label className="login-check">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Запомнить меня
        </label>

        {error && <div className="login-err">{error}</div>}

        <button type="submit" className="btn primary login-submit" disabled={submitting}>
          {submitting ? 'Вход…' : 'Войти'}
        </button>
      </form>
    </div>
  )
}