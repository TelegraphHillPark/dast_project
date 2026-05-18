import { useEffect, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api/client'
import { useAuthStore } from '../store/auth'
import Navbar from '../components/Navbar'

type TotpStep = 'idle' | 'setup' | 'disable'

interface ApiToken {
  id: string
  name: string
  is_active: boolean
  last_used_at: string | null
  created_at: string
}

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

  // ── 2FA ───────────────────────────────────────────────────────────────────
  const [totpStep, setTotpStep] = useState<TotpStep>('idle')
  const [totpSecret, setTotpSecret] = useState('')
  const [totpUri, setTotpUri] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [totpMsg, setTotpMsg] = useState('')
  const [totpErr, setTotpErr] = useState('')
  const [totpLoading, setTotpLoading] = useState(false)

  // ── avatar upload ─────────────────────────────────────────────────────────
  const fileRef = useRef<HTMLInputElement>(null)
  const [avatarLoading, setAvatarLoading] = useState(false)
  const [avatarErr, setAvatarErr] = useState('')

  // ── API tokens ────────────────────────────────────────────────────────────
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [newTokenName, setNewTokenName] = useState('')
  const [createdToken, setCreatedToken] = useState('')
  const [tokenErr, setTokenErr] = useState('')
  const [tokenLoading, setTokenLoading] = useState(false)

  useEffect(() => {
    api.get('/users/me/tokens').then(r => setTokens(r.data)).catch(() => {})
  }, [])

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

  async function startTotpSetup() {
    setTotpErr(''); setTotpMsg('')
    setTotpLoading(true)
    try {
      const { data } = await api.post('/auth/2fa/setup')
      setTotpSecret(data.secret)
      setTotpUri(data.qr_uri)
      setTotpStep('setup')
    } catch (err: any) {
      setTotpErr(err.response?.data?.detail ?? 'Ошибка настройки 2FA')
    } finally {
      setTotpLoading(false)
    }
  }

  async function confirmTotpEnable(e: React.FormEvent) {
    e.preventDefault()
    setTotpErr(''); setTotpMsg('')
    setTotpLoading(true)
    try {
      await api.post('/auth/2fa/enable', { secret: totpSecret, code: totpCode })
      setTotpMsg('Двухфакторная аутентификация включена')
      setTotpStep('idle'); setTotpCode('')
      setUser({ ...user!, totp_enabled: true })
    } catch (err: any) {
      setTotpErr(err.response?.data?.detail ?? 'Неверный код')
    } finally {
      setTotpLoading(false)
    }
  }

  async function confirmTotpDisable(e: React.FormEvent) {
    e.preventDefault()
    setTotpErr(''); setTotpMsg('')
    setTotpLoading(true)
    try {
      await api.post('/auth/2fa/disable', { secret: '', code: totpCode })
      setTotpMsg('Двухфакторная аутентификация отключена')
      setTotpStep('idle'); setTotpCode('')
      setUser({ ...user!, totp_enabled: false })
    } catch (err: any) {
      setTotpErr(err.response?.data?.detail ?? 'Неверный код')
    } finally {
      setTotpLoading(false)
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
      // не задаём Content-Type вручную — axios сам поставит multipart/form-data с boundary
      const { data } = await api.post('/users/me/avatar', form)
      setUser({ ...user!, avatar_url: data.avatar_url })
    } catch (err: any) {
      setAvatarErr(err.response?.data?.detail ?? 'Ошибка загрузки аватара')
    } finally {
      setAvatarLoading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleCreateToken(e: React.FormEvent) {
    e.preventDefault()
    setTokenErr(''); setCreatedToken('')
    setTokenLoading(true)
    try {
      const { data } = await api.post('/users/me/tokens', { name: newTokenName })
      setCreatedToken(data.token)
      setNewTokenName('')
      const r = await api.get('/users/me/tokens')
      setTokens(r.data)
    } catch (err: any) {
      setTokenErr(err.response?.data?.detail ?? 'Ошибка создания токена')
    } finally {
      setTokenLoading(false)
    }
  }

  async function handleRevokeToken(id: string) {
    try {
      await api.delete(`/users/me/tokens/${id}`)
      setTokens(t => t.filter(x => x.id !== id))
      if (createdToken) setCreatedToken('')
    } catch {
      setTokenErr('Ошибка отзыва токена')
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

        {/* 2FA */}
        <div style={card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>Двухфакторная аутентификация</h3>

          {totpStep === 'idle' && (
            <div>
              <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
                {user?.totp_enabled
                  ? '2FA включена. Вы можете отключить её, введя код из приложения.'
                  : '2FA не включена. Используйте приложение-аутентификатор (Google Authenticator, Authy) для повышения безопасности.'}
              </p>
              {totpMsg && <p style={{ color: '#4ade80', fontSize: 13, marginBottom: 10 }}>{totpMsg}</p>}
              {totpErr && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 10 }}>{totpErr}</p>}
              {user?.totp_enabled ? (
                <button style={{ ...btn, background: '#7f1d1d' }} onClick={() => { setTotpStep('disable'); setTotpErr(''); setTotpMsg('') }}>
                  Отключить 2FA
                </button>
              ) : (
                <button style={btn} onClick={startTotpSetup} disabled={totpLoading}>
                  {totpLoading ? 'Загрузка…' : 'Включить 2FA'}
                </button>
              )}
            </div>
          )}

          {totpStep === 'setup' && (
            <div>
              <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
                Отсканируйте QR-код в приложении-аутентификаторе или введите секрет вручную, затем введите 6-значный код для подтверждения.
              </p>
              <div style={{ marginBottom: 16, background: '#fff', display: 'inline-block', padding: 8, borderRadius: 8 }}>
                <QRCodeSVG value={totpUri} size={200} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>Секрет: </span>
                <code style={{ fontSize: 13, color: '#e2e8f0', background: '#0f172a', padding: '2px 8px', borderRadius: 4 }}>
                  {totpSecret}
                </code>
              </div>
              <form onSubmit={confirmTotpEnable} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input
                  style={{ ...inputStyle, width: 140, marginBottom: 0 }}
                  type="text"
                  placeholder="000000"
                  maxLength={6}
                  value={totpCode}
                  onChange={e => setTotpCode(e.target.value)}
                  required
                />
                <button style={btn} type="submit" disabled={totpLoading}>
                  {totpLoading ? 'Проверка…' : 'Подтвердить'}
                </button>
                <button type="button" style={{ ...btn, background: '#334155' }} onClick={() => setTotpStep('idle')}>
                  Отмена
                </button>
              </form>
              {totpErr && <p style={{ color: '#f87171', fontSize: 13, marginTop: 10 }}>{totpErr}</p>}
            </div>
          )}

          {totpStep === 'disable' && (
            <div>
              <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
                Введите текущий код из приложения-аутентификатора для отключения 2FA.
              </p>
              <form onSubmit={confirmTotpDisable} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input
                  style={{ ...inputStyle, width: 140, marginBottom: 0 }}
                  type="text"
                  placeholder="000000"
                  maxLength={6}
                  value={totpCode}
                  onChange={e => setTotpCode(e.target.value)}
                  required
                />
                <button style={{ ...btn, background: '#7f1d1d' }} type="submit" disabled={totpLoading}>
                  {totpLoading ? 'Отключение…' : 'Отключить'}
                </button>
                <button type="button" style={{ ...btn, background: '#334155' }} onClick={() => setTotpStep('idle')}>
                  Отмена
                </button>
              </form>
              {totpErr && <p style={{ color: '#f87171', fontSize: 13, marginTop: 10 }}>{totpErr}</p>}
            </div>
          )}
        </div>

        {/* API Tokens */}
        <div style={card}>
          <h3 style={{ margin: '0 0 4px', fontSize: 15 }}>Токены доступа (API)</h3>
          <p style={{ fontSize: 12, color: '#64748b', marginBottom: 16 }}>
            Используются для доступа к API без логина (например, из CI/CD или внешних скриптов).
          </p>

          <form onSubmit={handleCreateToken} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <input
              style={{ ...inputStyle, flex: 1, marginBottom: 0 }}
              placeholder="Название токена"
              value={newTokenName}
              onChange={e => setNewTokenName(e.target.value)}
              required
            />
            <button style={btn} type="submit" disabled={tokenLoading}>
              {tokenLoading ? '…' : 'Создать'}
            </button>
          </form>

          {createdToken && (
            <div style={{ background: '#0f172a', border: '1px solid #16a34a', borderRadius: 6, padding: 12, marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: '#4ade80', marginBottom: 6 }}>
                Токен создан. Сохраните его — он показывается один раз:
              </div>
              <code style={{ fontSize: 12, color: '#e2e8f0', wordBreak: 'break-all' }}>{createdToken}</code>
            </div>
          )}

          {tokenErr && <p style={{ color: '#f87171', fontSize: 12, marginBottom: 10 }}>{tokenErr}</p>}

          {tokens.length === 0 ? (
            <p style={{ fontSize: 13, color: '#475569' }}>Нет активных токенов</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tokens.map(t => (
                <div key={t.id} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  background: '#0f172a', borderRadius: 6, padding: '10px 14px',
                }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: t.is_active ? '#f1f5f9' : '#475569' }}>
                      {t.name}
                    </div>
                    <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                      Создан: {new Date(t.created_at).toLocaleDateString()}
                      {t.last_used_at && ` · Использован: ${new Date(t.last_used_at).toLocaleDateString()}`}
                    </div>
                  </div>
                  <button
                    onClick={() => handleRevokeToken(t.id)}
                    style={{ ...btn, background: '#7f1d1d', fontSize: 12, padding: '5px 12px' }}
                  >
                    Отозвать
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

      </main>
    </div>
  )
}
