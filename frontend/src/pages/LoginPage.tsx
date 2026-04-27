import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../store/auth'

type Step = 'login' | '2fa'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setTokens, setUser } = useAuthStore()

  const [step, setStep] = useState<Step>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [preAuthToken, setPreAuthToken] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/login', { email, password })
      if (data.requires_2fa) {
        setPreAuthToken(data.pre_auth_token)
        setStep('2fa')
      } else {
        await finalize(data.access_token, data.refresh_token)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  async function handle2FA(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/2fa/verify', { pre_auth_token: preAuthToken, code: totpCode })
      await finalize(data.access_token, data.refresh_token)
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Неверный код')
    } finally {
      setLoading(false)
    }
  }

  async function finalize(accessToken: string, refreshToken: string) {
    setTokens(accessToken, refreshToken)
    const { data: me } = await api.get('/users/me', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    setUser(me)
    navigate('/dashboard')
  }

  const s: React.CSSProperties = {
    maxWidth: 400, margin: '10vh auto', padding: 32,
    background: '#1e293b', borderRadius: 12,
  }
  const input: React.CSSProperties = {
    width: '100%', padding: '10px 12px', marginBottom: 12,
    background: '#0f172a', border: '1px solid #334155', borderRadius: 6,
    color: '#f1f5f9', fontSize: 14, boxSizing: 'border-box',
  }
  const btn: React.CSSProperties = {
    width: '100%', padding: '10px 0',
    background: '#2563eb', color: '#fff', border: 'none',
    borderRadius: 6, fontSize: 15, fontWeight: 600, cursor: 'pointer',
  }

  return (
    <div style={s}>
      <h1 style={{ marginBottom: 24, fontSize: 22 }}>DAST Analyzer</h1>

      {step === 'login' && (
        <form onSubmit={handleLogin}>
          <input style={input} type="email" placeholder="Эл. почта" value={email} onChange={e => setEmail(e.target.value)} required />
          <input style={input} type="password" placeholder="Пароль" value={password} onChange={e => setPassword(e.target.value)} required />
          {error && <p style={{ color: '#f87171', marginBottom: 12 }}>{error}</p>}
          <button style={btn} type="submit" disabled={loading}>
            {loading ? 'Вход…' : 'Войти'}
          </button>
          <div style={{ marginTop: 16, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>
            <span>Войти через: </span>
            <a href="/api/auth/oauth/github" style={{ marginRight: 12, color: '#94a3b8' }}>GitHub</a>
            <a href="/api/auth/oauth/google" style={{ color: '#94a3b8' }}>Google</a>
          </div>
        </form>
      )}

      {step === '2fa' && (
        <form onSubmit={handle2FA}>
          <p style={{ marginBottom: 16, color: '#94a3b8', fontSize: 14 }}>
            Введите 6-значный код из приложения-аутентификатора.
          </p>
          <input
            style={input}
            type="text"
            placeholder="000000"
            maxLength={6}
            value={totpCode}
            onChange={e => setTotpCode(e.target.value)}
            required
            autoFocus
          />
          {error && <p style={{ color: '#f87171', marginBottom: 12 }}>{error}</p>}
          <button style={btn} type="submit" disabled={loading}>
            {loading ? 'Проверка…' : 'Подтвердить'}
          </button>
          <button
            type="button"
            onClick={() => setStep('login')}
            style={{ ...btn, background: 'transparent', border: '1px solid #334155', marginTop: 8 }}
          >
            Назад
          </button>
        </form>
      )}
    </div>
  )
}
