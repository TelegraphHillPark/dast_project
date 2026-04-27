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

interface TokenItem {
  id: string
  owner_id: string
  owner_username: string
  name: string
  is_active: boolean
  last_used_at: string | null
  created_at: string
}

type Tab = 'users' | 'tokens'

export default function AdminPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('users')

  const [users, setUsers] = useState<UserItem[]>([])
  const [usersError, setUsersError] = useState('')

  const [tokens, setTokens] = useState<TokenItem[]>([])
  const [tokensError, setTokensError] = useState('')
  const [tokensLoaded, setTokensLoaded] = useState(false)

  useEffect(() => {
    api.get('/admin/users')
      .then(r => setUsers(r.data))
      .catch(e => setUsersError(e.response?.data?.detail ?? 'Не удалось загрузить пользователей'))
  }, [])

  useEffect(() => {
    if (tab === 'tokens' && !tokensLoaded) {
      api.get('/admin/tokens')
        .then(r => { setTokens(r.data); setTokensLoaded(true) })
        .catch(e => setTokensError(e.response?.data?.detail ?? 'Не удалось загрузить токены'))
    }
  }, [tab, tokensLoaded])

  async function toggleActive(user: UserItem) {
    await api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u))
  }

  async function changeRole(user: UserItem, role: string) {
    await api.patch(`/admin/users/${user.id}`, { role })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, role } : u))
  }

  async function revokeToken(tokenId: string) {
    await api.delete(`/admin/tokens/${tokenId}`)
    setTokens(prev => prev.map(t => t.id === tokenId ? { ...t, is_active: false } : t))
  }

  const nav: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 24px', background: '#1e293b', borderBottom: '1px solid #334155',
  }
  const btn: React.CSSProperties = {
    padding: '6px 14px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
  }
  const td: React.CSSProperties = { padding: '10px 12px', borderBottom: '1px solid #1e293b' }
  const th: React.CSSProperties = { ...td, background: '#0f172a', fontSize: 13, color: '#94a3b8', textAlign: 'left' }
  const tabBtn = (active: boolean): React.CSSProperties => ({
    padding: '8px 20px', marginRight: 4,
    background: active ? '#1e40af' : '#1e293b',
    color: active ? '#fff' : '#94a3b8',
    border: 'none', borderRadius: '6px 6px 0 0', fontSize: 14, cursor: 'pointer',
  })

  return (
    <div>
      <nav style={nav}>
        <span style={{ fontWeight: 700 }}>Панель администратора</span>
        <button style={btn} onClick={() => navigate('/dashboard')}>← Главная</button>
      </nav>

      <main style={{ padding: 32 }}>
        <div style={{ marginBottom: 0 }}>
          <button style={tabBtn(tab === 'users')} onClick={() => setTab('users')}>Пользователи</button>
          <button style={tabBtn(tab === 'tokens')} onClick={() => setTab('tokens')}>API-токены</button>
        </div>

        <div style={{ background: '#1e293b', borderRadius: '0 8px 8px 8px', padding: 24 }}>

          {tab === 'users' && (
            <>
              <h2 style={{ marginBottom: 16, marginTop: 0 }}>Пользователи</h2>
              {usersError && <p style={{ color: '#f87171' }}>{usersError}</p>}
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={th}>Имя пользователя</th>
                    <th style={th}>Эл. почта</th>
                    <th style={th}>Роль</th>
                    <th style={th}>Активен</th>
                    <th style={th}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} style={{ fontSize: 14 }}>
                      <td style={td}>{u.username}</td>
                      <td style={td}>{u.email}</td>
                      <td style={td}>
                        <select
                          value={u.role}
                          onChange={e => changeRole(u, e.target.value)}
                          style={{
                            background: '#0f172a', color: '#e2e8f0',
                            border: '1px solid #334155', borderRadius: 4,
                            padding: '2px 6px', fontSize: 13, cursor: 'pointer',
                          }}
                        >
                          <option value="user">Пользователь</option>
                          <option value="admin">Администратор</option>
                        </select>
                      </td>
                      <td style={td}>{u.is_active ? 'Да' : 'Нет'}</td>
                      <td style={td}>
                        <button
                          style={{ ...btn, background: u.is_active ? '#7f1d1d' : '#166534' }}
                          onClick={() => toggleActive(u)}
                        >
                          {u.is_active ? 'Деактивировать' : 'Активировать'}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && !usersError && (
                    <tr><td colSpan={5} style={{ ...td, color: '#94a3b8', textAlign: 'center' }}>Пользователей нет</td></tr>
                  )}
                </tbody>
              </table>
            </>
          )}

          {tab === 'tokens' && (
            <>
              <h2 style={{ marginBottom: 16, marginTop: 0 }}>API-токены</h2>
              {tokensError && <p style={{ color: '#f87171' }}>{tokensError}</p>}
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={th}>Название</th>
                    <th style={th}>Владелец</th>
                    <th style={th}>Активен</th>
                    <th style={th}>Последнее использование</th>
                    <th style={th}>Создан</th>
                    <th style={th}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {tokens.map(t => (
                    <tr key={t.id} style={{ fontSize: 14, opacity: t.is_active ? 1 : 0.5 }}>
                      <td style={td}>{t.name}</td>
                      <td style={td}>{t.owner_username}</td>
                      <td style={td}>{t.is_active ? 'Да' : 'Нет'}</td>
                      <td style={td}>{t.last_used_at ? new Date(t.last_used_at).toLocaleString('ru-RU') : '—'}</td>
                      <td style={td}>{new Date(t.created_at).toLocaleString('ru-RU')}</td>
                      <td style={td}>
                        {t.is_active && (
                          <button
                            style={{ ...btn, background: '#7f1d1d' }}
                            onClick={() => revokeToken(t.id)}
                          >
                            Отозвать
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {tokens.length === 0 && !tokensError && (
                    <tr><td colSpan={6} style={{ ...td, color: '#94a3b8', textAlign: 'center' }}>Токенов нет</td></tr>
                  )}
                </tbody>
              </table>
            </>
          )}

        </div>
      </main>
    </div>
  )
}
