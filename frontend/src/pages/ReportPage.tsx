import { useEffect, useState, useCallback, Fragment } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

interface ReportVuln {
  id: string
  vuln_type: string
  severity: string
  confidence: string
  url: string
  parameter: string | null
  method: string
  payload: string | null
  evidence: Record<string, any> | null
  recommendation: string | null
  found_at: string
}

interface Report {
  scan_id: string
  target_url: string
  status: string
  max_depth: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  crawl_stats: {
    visited_count: number
    forms_count: number
    js_routes_count: number
  } | null
  summary: {
    total_vulnerabilities: number
    by_severity: Record<string, number>
    by_type: Record<string, number>
  }
  vulnerabilities: ReportVuln[]
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
  broken_auth: 'Broken Auth',
  sensitive_data: 'Утечка данных',
  security_misconfiguration: 'Неверная конфигурация',
  other: 'Другое',
}

const SEV_LABEL: Record<string, string> = {
  critical: 'Критическая',
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
  info: 'Информационная',
}

// ── Evidence detail renderer ───────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      style={{
        padding: '2px 8px', fontSize: 11, borderRadius: 4, border: 'none',
        background: copied ? '#166534' : '#334155', color: copied ? '#4ade80' : '#94a3b8',
        cursor: 'pointer', marginLeft: 8, flexShrink: 0,
      }}
    >
      {copied ? '✓ скопировано' : 'копировать'}
    </button>
  )
}

function StatusBadge({ code }: { code: number }) {
  const color = code >= 500 ? '#dc2626' : code >= 400 ? '#d97706' : code >= 300 ? '#2563eb' : '#16a34a'
  return (
    <span style={{
      padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
      background: color + '22', color, border: `1px solid ${color}44`,
    }}>
      HTTP {code}
    </span>
  )
}

function CweBadge({ cwe }: { cwe: string }) {
  if (!cwe) return null
  const url = `https://cwe.mitre.org/data/definitions/${cwe.replace('CWE-', '')}.html`
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" style={{
      padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
      background: '#7c3aed22', color: '#a78bfa', border: '1px solid #7c3aed44',
      textDecoration: 'none', display: 'inline-block',
    }}>
      {cwe} ↗
    </a>
  )
}

function EvidenceDetails({ vuln }: { vuln: ReportVuln }) {
  const ev = vuln.evidence ?? {}

  // fields rendered specially — skip in generic table
  const SPECIAL = new Set(['curl', 'cwe', 'owasp', 'status_code', 'anomalies', 'body_snippet', 'confidence', 'missing_header'])

  const generic: [string, string][] = []
  if (vuln.payload) generic.push(['Payload', vuln.payload])
  for (const [k, v] of Object.entries(ev)) {
    if (!SPECIAL.has(k) && v !== null && v !== undefined) {
      generic.push([k, typeof v === 'object' ? JSON.stringify(v) : String(v)])
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Badges row */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {ev.status_code != null && <StatusBadge code={ev.status_code} />}
        {ev.cwe && <CweBadge cwe={ev.cwe} />}
        {ev.owasp && (
          <span style={{
            padding: '1px 8px', borderRadius: 10, fontSize: 11,
            background: '#0f172a', color: '#94a3b8', border: '1px solid #334155',
          }}>
            {ev.owasp}
          </span>
        )}
        {ev.missing_header && (
          <span style={{
            padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
            background: '#d9770622', color: '#fbbf24', border: '1px solid #d9770644',
          }}>
            ⚠ Отсутствует: {ev.missing_header}
          </span>
        )}
      </div>

      {/* Anomalies list */}
      {Array.isArray(ev.anomalies) && ev.anomalies.length > 0 && (
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Аномалии</div>
          <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: '#fbbf24' }}>
            {ev.anomalies.map((a: string, i: number) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      {/* Generic key-value pairs */}
      {generic.length > 0 && (
        <table style={{ borderCollapse: 'collapse', fontSize: 12, width: '100%' }}>
          <tbody>
            {generic.map(([k, v]) => (
              <tr key={k}>
                <td style={{ color: '#64748b', paddingRight: 12, whiteSpace: 'nowrap', verticalAlign: 'top', paddingBottom: 4, width: 1 }}>{k}</td>
                <td style={{ fontFamily: 'monospace', color: '#e2e8f0', wordBreak: 'break-all' }}>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Body snippet */}
      {ev.body_snippet && (
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Фрагмент ответа</div>
          <pre style={{
            margin: 0, padding: '8px 12px', background: '#0f172a', borderRadius: 6,
            fontSize: 11, color: '#94a3b8', overflowX: 'auto', maxHeight: 160,
            border: '1px solid #1e293b', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          }}>
            {ev.body_snippet}
          </pre>
        </div>
      )}

      {/* curl command */}
      {ev.curl && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: '#64748b' }}>curl команда для воспроизведения</span>
            <CopyButton text={ev.curl} />
          </div>
          <pre style={{
            margin: 0, padding: '8px 12px', background: '#0f172a', borderRadius: 6,
            fontSize: 11, color: '#4ade80', overflowX: 'auto',
            border: '1px solid #1e293b', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          }}>
            {ev.curl}
          </pre>
        </div>
      )}

    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState<string>('all')

  const toggleRow = useCallback((vid: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(vid) ? next.delete(vid) : next.add(vid)
      return next
    })
  }, [])

  useEffect(() => {
    if (!id) return
    api.get(`/scans/${id}/report`).then(({ data }) => setReport(data)).catch(() => {
      setError('Не удалось загрузить отчёт')
    })
  }, [id])

  function downloadJson() {
    if (!report) return
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `scan_${id}_report.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const card: React.CSSProperties = {
    background: '#1e293b', borderRadius: 10, padding: 24, marginBottom: 20,
  }
  const btn: React.CSSProperties = {
    minHeight: 44, minWidth: 44,
    padding: '7px 16px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
  }
  const th: React.CSSProperties = {
    padding: '8px 12px', background: '#0f172a', fontSize: 12,
    color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid #1e293b',
  }
  const td: React.CSSProperties = {
    padding: '8px 12px', borderBottom: '1px solid #0f172a', fontSize: 13,
  }

  if (error) return (
    <div>
      <Navbar title="Отчёт о сканировании" backTo={`/scans/${id}`} backLabel="← К сканированию" />
      <div style={{ padding: 32, color: '#f87171' }}>{error}</div>
    </div>
  )

  if (!report) return (
    <div>
      <Navbar title="Отчёт о сканировании" backTo={`/scans/${id}`} backLabel="← К сканированию" />
      <p style={{ padding: 32, color: '#94a3b8' }}>Загрузка…</p>
    </div>
  )

  const severities = ['critical', 'high', 'medium', 'low', 'info']
  const visibleVulns = filter === 'all'
    ? report.vulnerabilities
    : report.vulnerabilities.filter(v => v.severity === filter)

  return (
    <div>
      <Navbar title="Отчёт о сканировании" backTo={`/scans/${id}`} backLabel="← К сканированию" />

      <main style={{ padding: 32, maxWidth: 1100, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ ...card, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Цель сканирования</div>
            <div style={{ fontFamily: 'monospace', fontSize: 15, color: '#e2e8f0', wordBreak: 'break-all' }}>
              {report.target_url}
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: '#64748b' }}>
              ID: {report.scan_id}
              {report.started_at && (
                <> • Начало: {new Date(report.started_at).toLocaleString('ru-RU')}</>
              )}
              {report.finished_at && (
                <> • Окончание: {new Date(report.finished_at).toLocaleString('ru-RU')}</>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={btn} onClick={downloadJson}>⬇ JSON</button>
          </div>
        </div>

        {/* Summary stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16, marginBottom: 20 }}>
          <div style={{ ...card, padding: 16, marginBottom: 0, textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: report.summary.total_vulnerabilities > 0 ? '#f87171' : '#4ade80' }}>
              {report.summary.total_vulnerabilities}
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Уязвимостей</div>
          </div>
          {report.crawl_stats && (
            <>
              <div style={{ ...card, padding: 16, marginBottom: 0, textAlign: 'center' }}>
                <div style={{ fontSize: 28, fontWeight: 700 }}>{report.crawl_stats.visited_count}</div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Страниц обойдено</div>
              </div>
              <div style={{ ...card, padding: 16, marginBottom: 0, textAlign: 'center' }}>
                <div style={{ fontSize: 28, fontWeight: 700 }}>{report.crawl_stats.forms_count}</div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Форм найдено</div>
              </div>
            </>
          )}
        </div>

        {/* Severity breakdown + filter */}
        {Object.keys(report.summary.by_severity).length > 0 && (
          <div style={card}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>По критичности</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                onClick={() => setFilter('all')}
                style={{
                  padding: '6px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  border: '1px solid #334155', cursor: 'pointer',
                  background: filter === 'all' ? '#1e40af' : '#1e293b',
                  color: filter === 'all' ? '#fff' : '#94a3b8',
                }}
              >
                Все ({report.summary.total_vulnerabilities})
              </button>
              {severities.filter(s => report.summary.by_severity[s]).map(sev => (
                <button
                  key={sev}
                  onClick={() => setFilter(sev === filter ? 'all' : sev)}
                  style={{
                    padding: '6px 16px', borderRadius: 8, fontSize: 13, fontWeight: 700,
                    background: filter === sev ? (SEV_COLOR[sev] + '44') : (SEV_COLOR[sev] + '22'),
                    color: SEV_COLOR[sev],
                    border: `1px solid ${SEV_COLOR[sev]}${filter === sev ? '99' : '44'}`,
                    cursor: 'pointer',
                  }}
                >
                  {report.summary.by_severity[sev]} {SEV_LABEL[sev] ?? sev}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* By type breakdown */}
        {Object.keys(report.summary.by_type).length > 0 && (
          <div style={card}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>По типу уязвимости</h3>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {Object.entries(report.summary.by_type).map(([type, count]) => (
                <div key={type} style={{
                  padding: '8px 20px', borderRadius: 8, fontSize: 13,
                  background: '#334155', color: '#e2e8f0',
                }}>
                  {VULN_LABEL[type] ?? type}: {count}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Vulnerabilities table */}
        <div style={card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>
            Список уязвимостей ({visibleVulns.length}
            {filter !== 'all' ? ` из ${report.summary.total_vulnerabilities}` : ''})
          </h3>
          {visibleVulns.length === 0 ? (
            <p style={{ color: '#4ade80', margin: 0 }}>Уязвимостей не обнаружено.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 860 }}>
                <thead>
                  <tr>
                    {['Тип', 'Критичность', 'Уверенность', 'CWE', 'URL', 'Параметр', 'Метод', ''].map((h, i) => (
                      <th key={i} style={th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleVulns.map(v => {
                    const isOpen = expanded.has(v.id)
                    const cwe = v.evidence?.cwe ?? ''
                    return (
                      <Fragment key={v.id}>
                        <tr style={{ cursor: 'pointer' }} onClick={() => toggleRow(v.id)}>
                          <td style={td}>{VULN_LABEL[v.vuln_type] ?? v.vuln_type}</td>
                          <td style={td}>
                            <span style={{
                              padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                              background: (SEV_COLOR[v.severity] ?? '#64748b') + '22',
                              color: SEV_COLOR[v.severity] ?? '#64748b',
                            }}>
                              {(SEV_LABEL[v.severity] ?? v.severity).toUpperCase()}
                            </span>
                          </td>
                          <td style={td}>
                            <span style={{
                              padding: '1px 8px', borderRadius: 10, fontSize: 11,
                              background: v.confidence === 'high' ? '#16a34a22' : '#d9770622',
                              color: v.confidence === 'high' ? '#4ade80' : '#fbbf24',
                            }}>
                              {v.confidence === 'high' ? 'высокая' : 'низкая'}
                            </span>
                          </td>
                          <td style={td}>
                            {cwe ? (
                              <a
                                href={`https://cwe.mitre.org/data/definitions/${cwe.replace('CWE-', '')}.html`}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={e => e.stopPropagation()}
                                style={{
                                  padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                                  background: '#7c3aed22', color: '#a78bfa', border: '1px solid #7c3aed44',
                                  textDecoration: 'none', display: 'inline-block',
                                }}
                              >
                                {cwe}
                              </a>
                            ) : <span style={{ color: '#334155' }}>—</span>}
                          </td>
                          <td style={{ ...td, fontFamily: 'monospace', fontSize: 11, color: '#94a3b8', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {v.url}
                          </td>
                          <td style={{ ...td, color: '#94a3b8' }}>{v.parameter ?? '—'}</td>
                          <td style={{ ...td, color: '#94a3b8' }}>{v.method}</td>
                          <td style={{ ...td, textAlign: 'center', color: '#64748b', fontSize: 14, width: 30 }}>
                            {isOpen ? '▲' : '▼'}
                          </td>
                        </tr>
                        {isOpen && (
                          <tr style={{ background: '#0f172a' }}>
                            <td colSpan={8} style={{ padding: '12px 16px', borderBottom: '1px solid #1e293b' }}>
                              <EvidenceDetails vuln={v} />
                              {v.recommendation && (
                                <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, background: '#1e293b', fontSize: 12, color: '#94a3b8', borderLeft: '3px solid #1e40af' }}>
                                  <strong style={{ color: '#60a5fa' }}>Рекомендация:</strong> {v.recommendation}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </main>
    </div>
  )
}
