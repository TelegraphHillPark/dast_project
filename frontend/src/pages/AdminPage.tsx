import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface UserItem {
  id: string
  email: string
  username: string
  role: string
  is_active: boolean
}

export default function AdminPage() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<UserItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/admin/users')
      .then(r => setUsers(r.data))
      .catch(e => setError(e.response?.data?.detail ?? 'Failed to load users'))
  }, [])

  async function toggleActive(user: UserItem) {
    await api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u))
  }

  const nav: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 24px', background: '#1e293b', borderBottom: '1px solid #334155',
  }
  const btn: React.CSSProperties = {
    padding: '6px 14px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13,
  }
  const td: React.CSSProperties = { padding: '10px 12px', borderBottom: '1px solid #1e293b' }

  return (
    <div>
      <nav style={nav}>
        <span style={{ fontWeight: 700 }}>Admin Panel</span>
        <button style={btn} onClick={() => navigate('/dashboard')}>← Dashboard</button>
      </nav>

      <main style={{ padding: 32 }}>
        <h2 style={{ marginBottom: 20 }}>Users</h2>
        {error && <p style={{ color: '#f87171' }}>{error}</p>}
        <table style={{ width: '100%', borderCollapse: 'collapse', background: '#1e293b', borderRadius: 8 }}>
          <thead>
            <tr style={{ background: '#0f172a', fontSize: 13, color: '#94a3b8' }}>
              <th style={td}>Username</th>
              <th style={td}>Email</th>
              <th style={td}>Role</th>
              <th style={td}>Active</th>
              <th style={td}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} style={{ fontSize: 14 }}>
                <td style={td}>{u.username}</td>
                <td style={td}>{u.email}</td>
                <td style={td}>{u.role}</td>
                <td style={td}>{u.is_active ? '✓' : '✗'}</td>
                <td style={td}>
                  <button style={{ ...btn, background: u.is_active ? '#7f1d1d' : '#166534' }} onClick={() => toggleActive(u)}>
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  )
}
