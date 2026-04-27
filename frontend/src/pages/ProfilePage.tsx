import { useRef, useState } from 'react'
import { api } from '../api/client'
import { useAuthStore } from '../store/auth'
import Navbar from '../components/Navbar'

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()

  // ── profile edit ──────────────────────────────────────────────────────────
  const [username, setUsername] = useState(user?.username ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [profileMsg, setProfileMsg] = useState('')
  const [profileErr, setProfileErr] = useState('')
  const [profileLoading, setProfileLoading] = useState(false)

  // ── password change ───────────────────────────────────────────────────────
  const [curPwd, setCurPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [pwdMsg, setPwdMsg] = useState('')
  const [pwdErr, setPwdErr] = useState('')
  const [pwdLoading, setPwdLoading] = useState(false)

  // ── avatar upload ─────────────────────────────────────────────────────────
  const fileRef = useRef<HTMLInputElement>(null)
  const [avatarLoading, setAvatarLoading] = useState(false)
  const [avatarErr, setAvatarErr] = useState('')

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault()
    setProfileMsg(''); setProfileErr('')
    setProfileLoading(true)
    try {
      const { data } = await api.patch('/users/me', { username, email })
      setUser({ ...user!, username: data.username, email: data.email })
      setProfileMsg('Профиль обновлён')
    } catch (err: any) {
      setProfileErr(err.response?.data?.detail ?? 'Ошибка обновления')
    } finally {
      setProfileLoading(false)
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault()
    setPwdMsg(''); setPwdErr('')
    setPwdLoading(true)
    try {
      await api.post('/users/me/change-password', { current_password: curPwd, new_password: newPwd })
      setPwdMsg('Пароль изменён')
      setCurPwd(''); setNewPwd('')
    } catch (err: any) {
      setPwdErr(err.response?.data?.detail ?? 'Ошибка смены пароля')
    } finally {
      setPwdLoading(false)
    }
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setAvatarErr('')
    setAvatarLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post('/users/me/avatar', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setUser({ ...user!, avatar_url: data.avatar_url })
    } catch (err: any) {
      setAvatarErr(err.response?.data?.detail ?? 'Ошибка загрузки аватара')
    } finally {
      setAvatarLoading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const card: React.CSSProperties = {
    background: '#1e293b', borderRadius: 10, padding: 24, marginBottom: 20,
  }
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '9px 12px', marginBottom: 12,
    background: '#0f172a', border: '1px solid #334155', borderRadius: 6,
    color: '#f1f5f9', fontSize: 14, boxSizing: 'border-box',
  }
  const btn: React.CSSProperties = {
    padding: '8px 20px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 14, cursor: 'pointer',
  }
  const label: React.CSSProperties = { display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }

  return (
    <div>
      <Navbar title="Профиль" backTo="/dashboard" backLabel="← Главная" />

      <main style={{ padding: 32, maxWidth: 560, margin: '0 auto' }}>

        {/* Avatar */}
        <div style={{ ...card, display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{ position: 'relative', flexShrink: 0 }}>
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt="avatar"
                style={{ width: 80, height: 80, borderRadius: '50%', objectFit: 'cover', border: '3px solid #334155' }}
              />
            ) : (
              <div style={{
                width: 80, height: 80, borderRadius: '50%',
                background: 'linear-gradient(135deg, #1e40af, #7c3aed)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 28, fontWeight: 700, color: '#fff', border: '3px solid #334155',
              }}>
                {user?.username.slice(0, 2).toUpperCase()}
              </div>
            )}
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{user?.username}</div>
            <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>{user?.email}</div>
            <button
              style={{ ...btn, fontSize: 13, padding: '6px 14px', background: '#334155' }}
              onClick={() => fileRef.current?.click()}
              disabled={avatarLoading}
            >
              {avatarLoading ? 'Загрузка…' : 'Сменить аватар'}
            </button>
            {avatarErr && <div style={{ color: '#f87171', fontSize: 12, marginTop: 6 }}>{avatarErr}</div>}
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              style={{ display: 'none' }}
              onChange={handleAvatarChange}
            />
          </div>
        </div>

        {/* Profile info */}
        <div style={card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>Данные профиля</h3>
          <form onSubmit={handleProfileSave}>
            <label style={label}>Имя пользователя</label>
            <input style={inputStyle} value={username} onChange={e => setUsername(e.target.value)} />
            <label style={label}>Эл. почта</label>
            <input style={inputStyle} type="email" value={email} onChange={e => setEmail(e.target.value)} />
            {profileMsg && <p style={{ color: '#4ade80', fontSize: 13, marginBottom: 8 }}>{profileMsg}</p>}
            {profileErr && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 8 }}>{profileErr}</p>}
            <button style={btn} type="submit" disabled={profileLoading}>
              {profileLoading ? 'Сохранение…' : 'Сохранить'}
            </button>
          </form>
        </div>

        {/* Password */}
        <div style={card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>Смена пароля</h3>
          <form onSubmit={handlePasswordChange}>
            <label style={label}>Текущий пароль</label>
            <input style={inputStyle} type="password" value={curPwd} onChange={e => setCurPwd(e.target.value)} required />
            <label style={label}>Новый пароль</label>
            <input style={inputStyle} type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)} required minLength={8} />
            {pwdMsg && <p style={{ color: '#4ade80', fontSize: 13, marginBottom: 8 }}>{pwdMsg}</p>}
            {pwdErr && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 8 }}>{pwdErr}</p>}
            <button style={btn} type="submit" disabled={pwdLoading}>
              {pwdLoading ? 'Смена…' : 'Сменить пароль'}
            </button>
          </form>
        </div>

      </main>
    </div>
  )
}
