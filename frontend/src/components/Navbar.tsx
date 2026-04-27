import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../store/auth'

interface NavbarProps {
  title?: string
  backTo?: string
  backLabel?: string
}

function Avatar({ username, avatarUrl }: { username: string; avatarUrl: string | null }) {
  const initials = username.slice(0, 2).toUpperCase()
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={username}
        style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover', border: '2px solid #334155' }}
      />
    )
  }
  return (
    <div style={{
      width: 32, height: 32, borderRadius: '50%',
      background: 'linear-gradient(135deg, #1e40af, #7c3aed)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 12, fontWeight: 700, color: '#fff', flexShrink: 0,
      border: '2px solid #334155',
    }}>
      {initials}
    </div>
  )
}

export default function Navbar({ title = 'DAST Analyzer', backTo, backLabel }: NavbarProps) {
  const navigate = useNavigate()
  const { user, refreshToken, logout } = useAuthStore()

  async function handleLogout() {
    if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {})
    logout()
    navigate('/login')
  }

  const nav: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 24px', background: '#1e293b', borderBottom: '1px solid #334155',
    position: 'sticky', top: 0, zIndex: 10,
  }
  const btn: React.CSSProperties = {
    padding: '5px 12px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
  }

  return (
    <nav style={nav}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {backTo && (
          <button style={{ ...btn, background: 'transparent', border: '1px solid #334155', color: '#94a3b8' }} onClick={() => navigate(backTo)}>
            {backLabel ?? '← Назад'}
          </button>
        )}
        <span style={{ fontWeight: 700, fontSize: 16 }}>{title}</span>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        {user?.role === 'admin' && (
          <button style={btn} onClick={() => navigate('/admin')}>Администратор</button>
        )}
        <button
          style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: '1px solid #334155', borderRadius: 8, padding: '4px 10px', cursor: 'pointer', color: '#e2e8f0' }}
          onClick={() => navigate('/profile')}
        >
          <Avatar username={user?.username ?? '?'} avatarUrl={user?.avatar_url ?? null} />
          <span style={{ fontSize: 13 }}>{user?.username}</span>
        </button>
        <button style={{ ...btn, background: '#7f1d1d' }} onClick={handleLogout}>Выйти</button>
      </div>
    </nav>
  )
}
