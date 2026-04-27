import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

// ── Types ────────────────────────────────────────────────────────────────────

type ScanStatus = 'pending' | 'running' | 'paused' | 'finished' | 'failed'

interface Vulnerability {
  id: string
  vuln_type: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  url: string
  parameter: string | null
  method: string
  payload: string | null
  recommendation: string | null
  created_at: string
}

interface ScanDetail {
  id: string
  target_url: string
  status: ScanStatus
  max_depth: number
  timeout_seconds: number
  excluded_paths: string[]
  created_at: string
  started_at: string | null
  finished_at: string | null
  vuln_count: number
  vulnerabilities: Vulnerability[]
  crawl_stats: {
    visited_count: number
    forms_count: number
    js_routes_count: number
    visited_urls: string[]
  } | null
}

// ── Style helpers ─────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<ScanStatus, string> = {
  pending: 'Ожидание',
  running: 'Выполняется',
  paused: 'Приостановлен',
  finished: 'Завершён',
  failed: 'Ошибка',
}

const STATUS_COLOR: Record<ScanStatus, string> = {
  pending: '#64748b',
  running: '#2563eb',
  paused: '#d97706',
  finished: '#16a34a',
  failed: '#dc2626',
}

const SEV_COLOR: Record<string, string> = {
  critical: '#7c3aed',
  high: '#dc2626',
  medium: '#d97706',
  low: '#2563eb',
  info: '#64748b',
}

const VULN_LABEL: Record<string, string> = {
  sqli: 'SQL-инъекция',
  xss: 'XSS',
  ssrf: 'SSRF',
  open_redirect: 'Открытый редирект',
  header_injection: 'Header Injection',
  broken_auth: 'Уязвимая авторизация',
  sensitive_data: 'Утечка данных',
  security_misconfiguration: 'Неверная конфигурация',
  other: 'Прочее',
}

// ── Shared styles ─────────────────────────────────────────────────────────────

const btn: React.CSSProperties = {
  padding: '6px 14px', background: '#1e40af', color: '#fff',
  border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
}
const input: React.CSSProperties = {
  width: '100%', padding: '9px 12px', marginBottom: 12,
  background: '#0f172a', border: '1px solid #334155', borderRadius: 6,
  color: '#f1f5f9', fontSize: 14, boxSizing: 'border-box',
}
const card: React.CSSProperties = {
  background: '#1e293b', borderRadius: 10, padding: 24, marginBottom: 20,
}

// ── Create form ───────────────────────────────────────────────────────────────

function CreateScanForm() {
  const navigate = useNavigate()

  const [targetUrl, setTargetUrl] = useState('')
  const [maxDepth, setMaxDepth] = useState(3)
  const [timeout, setTimeout] = useState(3600)
  const [excludedPaths, setExcludedPaths] = useState('')
  const [authType, setAuthType] = useState('none')
  const [cookie, setCookie] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [bearerToken, setBearerToken] = useState('')
  const [loginUrl, setLoginUrl] = useState('')
  const [usernameField, setUsernameField] = useState('username')
  const [passwordField, setPasswordField] = useState('password')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const auth_config: Record<string, string> = { type: authType }
      if (authType === 'cookie') auth_config.cookie = cookie
      if (authType === 'basic') { auth_config.username = username; auth_config.password = password }
      if (authType === 'bearer') auth_config.bearer_token = bearerToken
      if (authType === 'form') {
        auth_config.login_url = loginUrl
        auth_config.username = username
        auth_config.password = password
        auth_config.username_field = usernameField
        auth_config.password_field = passwordField
      }

      const { data } = await api.post('/scans', {
        target_url: targetUrl,
        max_depth: maxDepth,
        timeout_seconds: timeout,
        excluded_paths: excludedPaths.split('\n').map(s => s.trim()).filter(Boolean),
        auth_config,
      })
      navigate(`/scans/${data.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Ошибка создания сканирования')
    } finally {
      setLoading(false)
    }
  }

  const select: React.CSSProperties = { ...input, marginBottom: 0 }
  const label: React.CSSProperties = { display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }
  const row: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }

  return (
    <div>
      <Navbar title="Новое сканирование" backTo="/dashboard" backLabel="← Назад" />

      <main style={{ padding: 32, maxWidth: 720, margin: '0 auto' }}>
        <form onSubmit={handleSubmit}>
          <div style={card}>
            <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>Цель сканирования</h3>
            <label style={label}>URL цели *</label>
            <input
              style={input}
              type="url"
              placeholder="https://example.com"
              value={targetUrl}
              onChange={e => setTargetUrl(e.target.value)}
              required
            />
            <div style={row}>
              <div>
                <label style={label}>Глубина обхода (1–10)</label>
                <input
                  style={{ ...input, marginBottom: 0 }}
                  type="number" min={1} max={10}
                  value={maxDepth}
                  onChange={e => setMaxDepth(Number(e.target.value))}
                />
              </div>
              <div>
                <label style={label}>Таймаут (сек)</label>
                <input
                  style={{ ...input, marginBottom: 0 }}
                  type="number" min={60} max={86400}
                  value={timeout}
                  onChange={e => setTimeout(Number(e.target.value))}
                />
              </div>
            </div>
          </div>

          <div style={card}>
            <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>Исключённые пути</h3>
            <label style={label}>Один путь на строку (например /logout)</label>
            <textarea
              style={{ ...input, height: 80, resize: 'vertical', marginBottom: 0 }}
              placeholder={'/logout\n/admin'}
              value={excludedPaths}
              onChange={e => setExcludedPaths(e.target.value)}
            />
          </div>

          <div style={card}>
            <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>Аутентификация</h3>
            <label style={label}>Тип аутентификации</label>
            <select
              style={{ ...select, marginBottom: 16 }}
              value={authType}
              onChange={e => setAuthType(e.target.value)}
            >
              <option value="none">Без аутентификации</option>
              <option value="cookie">Cookie</option>
              <option value="basic">HTTP Basic Auth</option>
              <option value="bearer">Bearer Token</option>
              <option value="form">Form Login</option>
            </select>

            {authType === 'cookie' && (
              <>
                <label style={label}>Cookie-строка</label>
                <input style={input} placeholder="session=abc123; token=xyz" value={cookie} onChange={e => setCookie(e.target.value)} />
              </>
            )}

            {authType === 'basic' && (
              <div style={row}>
                <div>
                  <label style={label}>Логин</label>
                  <input style={{ ...input, marginBottom: 0 }} value={username} onChange={e => setUsername(e.target.value)} />
                </div>
                <div>
                  <label style={label}>Пароль</label>
                  <input style={{ ...input, marginBottom: 0 }} type="password" value={password} onChange={e => setPassword(e.target.value)} />
                </div>
              </div>
            )}

            {authType === 'bearer' && (
              <>
                <label style={label}>Bearer Token</label>
                <input style={input} placeholder="eyJ..." value={bearerToken} onChange={e => setBearerToken(e.target.value)} />
              </>
            )}

            {authType === 'form' && (
              <>
                <label style={label}>URL страницы входа</label>
                <input style={input} type="url" placeholder="https://example.com/login" value={loginUrl} onChange={e => setLoginUrl(e.target.value)} />
                <div style={row}>
                  <div>
                    <label style={label}>Логин</label>
                    <input style={{ ...input, marginBottom: 0 }} value={username} onChange={e => setUsername(e.target.value)} />
                  </div>
                  <div>
                    <label style={label}>Пароль</label>
                    <input style={{ ...input, marginBottom: 0 }} type="password" value={password} onChange={e => setPassword(e.target.value)} />
                  </div>
                </div>
                <div style={{ ...row, marginTop: 12 }}>
                  <div>
                    <label style={label}>Имя поля логина</label>
                    <input style={{ ...input, marginBottom: 0 }} value={usernameField} onChange={e => setUsernameField(e.target.value)} />
                  </div>
                  <div>
                    <label style={label}>Имя поля пароля</label>
                    <input style={{ ...input, marginBottom: 0 }} value={passwordField} onChange={e => setPasswordField(e.target.value)} />
                  </div>
                </div>
              </>
            )}
          </div>

          {error && <p style={{ color: '#f87171', marginBottom: 12 }}>{error}</p>}

          <button
            type="submit"
            disabled={loading}
            style={{ ...btn, width: '100%', padding: '12px 0', fontSize: 15, fontWeight: 600 }}
          >
            {loading ? 'Создание…' : 'Запустить сканирование'}
          </button>
        </form>
      </main>
    </div>
  )
}

// ── Detail view ───────────────────────────────────────────────────────────────

function ScanDetail({ scanId }: { scanId: string }) {
  const navigate = useNavigate()
  const [scan, setScan] = useState<ScanDetail | null>(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      const { data } = await api.get(`/scans/${scanId}`)
      setScan(data)
    } catch {
      setError('Не удалось загрузить данные сканирования')
    }
  }

  useEffect(() => { load() }, [scanId])

  // Poll while active
  useEffect(() => {
    if (!scan) return
    if (scan.status !== 'pending' && scan.status !== 'running') return
    const id = setInterval(load, 4000)
    return () => clearInterval(id)
  }, [scan?.status])

  async function handlePause() {
    await api.post(`/scans/${scanId}/pause`)
    load()
  }

  async function handleResume() {
    await api.post(`/scans/${scanId}/resume`)
    load()
  }

  if (error) return (
    <div style={{ padding: 32 }}>
      <p style={{ color: '#f87171' }}>{error}</p>
      <button style={btn} onClick={() => navigate('/dashboard')}>← Назад</button>
    </div>
  )

  if (!scan) return <p style={{ padding: 32, color: '#94a3b8' }}>Загрузка…</p>

  const statusColor = STATUS_COLOR[scan.status]

  return (
    <div>
      <Navbar title="Сканирование" backTo="/dashboard" backLabel="← К списку" />

      <main style={{ padding: 32 }}>
        {/* Header card */}
        <div style={{ ...card, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Цель</div>
            <div style={{ fontFamily: 'monospace', fontSize: 15, color: '#e2e8f0', wordBreak: 'break-all' }}>
              {scan.target_url}
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: '#64748b' }}>
              ID: {scan.id} • Создан: {new Date(scan.created_at).toLocaleString('ru-RU')}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
            <span style={{
              padding: '4px 14px', borderRadius: 14, fontSize: 13, fontWeight: 700,
              background: statusColor + '22', color: statusColor,
              border: `1px solid ${statusColor}44`,
            }}>
              {STATUS_LABEL[scan.status]}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              {scan.status === 'running' && (
                <button style={{ ...btn, background: '#92400e' }} onClick={handlePause}>⏸ Пауза</button>
              )}
              {scan.status === 'paused' && (
                <button style={{ ...btn, background: '#166534' }} onClick={handleResume}>▶ Продолжить</button>
              )}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16, marginBottom: 20 }}>
          {[
            { label: 'Глубина', value: scan.max_depth },
            { label: 'Уязвимостей', value: scan.vuln_count, highlight: scan.vuln_count > 0 },
            { label: 'Страниц обойдено', value: scan.crawl_stats?.visited_count ?? '—' },
            { label: 'Форм найдено', value: scan.crawl_stats?.forms_count ?? '—' },
            { label: 'JS-маршрутов', value: scan.crawl_stats?.js_routes_count ?? '—' },
          ].map(({ label, value, highlight }) => (
            <div key={label} style={{ ...card, padding: 16, marginBottom: 0, textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: highlight ? '#f87171' : '#e2e8f0' }}>{value}</div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Vulnerabilities */}
        <div style={card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>
            Найденные уязвимости {scan.vuln_count > 0 && `(${scan.vuln_count})`}
          </h3>
          {scan.vulnerabilities.length === 0 ? (
            <p style={{ color: '#94a3b8', margin: 0 }}>
              {scan.status === 'finished' ? 'Уязвимостей не найдено.' : 'Уязвимости появятся по мере сканирования.'}
            </p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Тип', 'Критичность', 'URL', 'Параметр', 'Метод'].map(h => (
                    <th key={h} style={{
                      padding: '8px 12px', background: '#0f172a', fontSize: 12,
                      color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid #1e293b',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scan.vulnerabilities.map(v => (
                  <tr key={v.id}>
                    <td style={{ padding: '8px 12px', borderBottom: '1px solid #0f172a', fontSize: 13 }}>
                      {VULN_LABEL[v.vuln_type] ?? v.vuln_type}
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: '1px solid #0f172a' }}>
                      <span style={{
                        padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                        background: (SEV_COLOR[v.severity] ?? '#64748b') + '22',
                        color: SEV_COLOR[v.severity] ?? '#64748b',
                      }}>
                        {v.severity.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: '1px solid #0f172a', fontSize: 11, fontFamily: 'monospace', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#94a3b8' }}>
                      {v.url}
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: '1px solid #0f172a', fontSize: 12, color: '#94a3b8' }}>
                      {v.parameter ?? '—'}
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: '1px solid #0f172a', fontSize: 12, color: '#94a3b8' }}>
                      {v.method}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Discovered URLs */}
        {scan.crawl_stats?.visited_urls && scan.crawl_stats.visited_urls.length > 0 && (
          <div style={card}>
            <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>
              Обнаруженные страницы ({scan.crawl_stats.visited_count})
            </h3>
            <div style={{ maxHeight: 220, overflowY: 'auto', fontFamily: 'monospace', fontSize: 12, color: '#64748b', lineHeight: 1.8 }}>
              {scan.crawl_stats.visited_urls.map(url => (
                <div key={url}>{url}</div>
              ))}
              {scan.crawl_stats.visited_count > 500 && (
                <div style={{ color: '#475569', marginTop: 4 }}>… и ещё {scan.crawl_stats.visited_count - 500} страниц</div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// ── Router ────────────────────────────────────────────────────────────────────

export default function ScanPage() {
  const { id } = useParams<{ id: string }>()
  return id ? <ScanDetail scanId={id} /> : <CreateScanForm />
}
