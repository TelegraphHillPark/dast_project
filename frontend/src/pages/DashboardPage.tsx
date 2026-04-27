import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../store/auth'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { user, refreshToken, logout } = useAuthStore()

  async function handleLogout() {
    if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {})
    logout()
    navigate('/login')
  }

  const nav: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 24px', background: '#1e293b', borderBottom: '1px solid #334155',
  }
  const btn: React.CSSProperties = {
    padding: '6px 14px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
  }

  return (
    <div>
      <nav style={nav}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>DAST Analyzer</span>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: '#94a3b8' }}>{user?.username}</span>
          {user?.role === 'admin' && (
            <button style={btn} onClick={() => navigate('/admin')}>Администратор</button>
          )}
          <button style={{ ...btn, background: '#7f1d1d' }} onClick={handleLogout}>Выйти</button>
        </div>
      </nav>

      <main style={{ padding: 32 }}>
        <h2 style={{ marginBottom: 24 }}>Сканирования</h2>
        <p style={{ color: '#94a3b8' }}>Сканирований пока нет. Управление сканами появится в Спринте 3.</p>
      </main>
    </div>
  )
}
