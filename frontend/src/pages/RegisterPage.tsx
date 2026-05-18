import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'

export default function RegisterPage() {
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== password2) {
      setError('Пароли не совпадают')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/register', { email, username, password })
      navigate('/login')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join('; '))
      } else {
        setError(detail ?? 'Ошибка регистрации')
      }
    } finally {
      setLoading(false)
    }
  }

  const s: React.CSSProperties = {
    maxWidth: 400, margin: '10vh auto', padding: 32,
    background: '#1e293b', borderRadius: 12,
  }
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px', marginBottom: 12,
    background: '#0f172a', border: '1px solid #334155', borderRadius: 6,
    color: '#f1f5f9', fontSize: 14, boxSizing: 'border-box',
  }
  const btn: React.CSSProperties = {
    width: '100%', padding: '10px 0',
    background: '#2563eb', color: '#fff', border: 'none',
    borderRadius: 6, fontSize: 15, fontWeight: 600, cursor: 'pointer',
  }
  const label: React.CSSProperties = { display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }

  return (
    <div style={s}>
      <h1 style={{ marginBottom: 8, fontSize: 22 }}>DAST Analyzer</h1>
      <p style={{ color: '#64748b', fontSize: 14, marginBottom: 24 }}>Создание учётной записи</p>

      <form onSubmit={handleSubmit}>
        <label style={label}>Эл. почта</label>
        <input
          style={inputStyle}
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
        <label style={label}>Имя пользователя</label>
        <input
          style={inputStyle}
          type="text"
          placeholder="username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          required
          minLength={3}
        />
        <label style={label}>Пароль</label>
        <input
          style={inputStyle}
          type="password"
          placeholder="Минимум 8 символов"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <label style={label}>Повторите пароль</label>
        <input
          style={inputStyle}
          type="password"
          placeholder="Повторите пароль"
          value={password2}
          onChange={e => setPassword2(e.target.value)}
          required
        />

        {error && <p style={{ color: '#f87171', marginBottom: 12, fontSize: 13 }}>{error}</p>}

        <button style={btn} type="submit" disabled={loading}>
          {loading ? 'Регистрация…' : 'Зарегистрироваться'}
        </button>
      </form>

      <div style={{ marginTop: 20, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>
        Уже есть аккаунт?{' '}
        <Link to="/login" style={{ color: '#60a5fa' }}>Войти</Link>
      </div>
    </div>
  )
}
