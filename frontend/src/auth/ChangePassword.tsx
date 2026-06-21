import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import type { ApiError } from '../api/client'

export function ChangePassword() {
  const navigate = useNavigate()
  const { changePassword } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const tooShort = next.length > 0 && next.length < 8

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (next.length < 8) {
      setError('Новый пароль должен содержать минимум 8 символов')
      return
    }
    setSubmitting(true)
    try {
      await changePassword(current, next)
      navigate('/', { replace: true })
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr?.status === 400 || apiErr?.status === 401) {
        setError('Не удалось сменить пароль. Проверьте текущий пароль.')
      } else {
        setError('Ошибка смены пароля. Попробуйте позже.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-head">
          <div className="login-mark warn">СНАБ</div>
          <h1 className="warn">Требуется смена пароля</h1>
          <p>Задайте новый пароль, прежде чем продолжить.</p>
        </div>

        <label className="login-field">
          <span>Текущий пароль</span>
          <input
            type="password"
            className="rep-sel"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        <label className="login-field">
          <span>Новый пароль</span>
          <input
            type="password"
            className="rep-sel"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <small className="login-hint">Минимум 8 символов</small>
          {tooShort && <small className="login-hint bad">Слишком короткий пароль</small>}
        </label>

        {error && <div className="login-err">{error}</div>}

        <button
          type="submit"
          className="btn primary login-submit"
          disabled={submitting || next.length < 8}
        >
          {submitting ? 'Сохранение…' : 'Сменить пароль'}
        </button>
      </form>
    </div>
  )
}