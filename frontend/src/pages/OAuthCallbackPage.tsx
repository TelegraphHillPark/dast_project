import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../store/auth'

export default function OAuthCallbackPage() {
  const [params] = useSearchParams()
  const { setTokens, setUser } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    const access = params.get('access_token')
    const refresh = params.get('refresh_token')

    if (!access || !refresh) {
      navigate('/login', { replace: true })
      return
    }

    setTokens(access, refresh)
    api.get('/users/me')
      .then(r => { setUser(r.data); navigate('/dashboard', { replace: true }) })
      .catch(() => navigate('/login', { replace: true }))
  }, [])

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#0f172a', color: '#f1f5f9', fontSize: 18,
    }}>
      Выполняется вход…
    </div>
  )
}
