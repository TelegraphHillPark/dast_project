import { useEffect, useState } from 'react'
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
}

const SEV_LABEL: Record<string, string> = {
  critical: 'Критическая',
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
  info: 'Информационная',
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')

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
            <a
              href={`/api/scans/${id}/report.pdf`}
              download={`scan_${id}_report.pdf`}
              style={{ ...btn, textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}
            >
              ⬇ PDF
            </a>
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

        {/* Severity breakdown */}
        {Object.keys(report.summary.by_severity).length > 0 && (
          <div style={card}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>По критичности</h3>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {Object.entries(report.summary.by_severity).map(([sev, count]) => (
                <div key={sev} style={{
                  padding: '8px 20px', borderRadius: 8, fontSize: 14, fontWeight: 700,
                  background: (SEV_COLOR[sev] ?? '#64748b') + '22',
                  color: SEV_COLOR[sev] ?? '#64748b',
                  border: `1px solid ${(SEV_COLOR[sev] ?? '#64748b')}44`,
                }}>
                  {count} {SEV_LABEL[sev] ?? sev}
                </div>
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
            Список уязвимостей ({report.summary.total_vulnerabilities})
          </h3>
          {report.vulnerabilities.length === 0 ? (
            <p style={{ color: '#4ade80', margin: 0 }}>Уязвимостей не обнаружено.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 800 }}>
                <thead>
                  <tr>
                    {['Тип', 'Критичность', 'Уверенность', 'URL', 'Параметр', 'Метод', 'Рекомендация'].map(h => (
                      <th key={h} style={th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.vulnerabilities.map(v => (
                    <tr key={v.id}>
                      <td style={td}>{VULN_LABEL[v.vuln_type] ?? v.vuln_type}</td>
                      <td style={td}>
                        <span style={{
                          padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                          background: (SEV_COLOR[v.severity] ?? '#64748b') + '22',
                          color: SEV_COLOR[v.severity] ?? '#64748b',
                        }}>
                          {v.severity.toUpperCase()}
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
                      <td style={{ ...td, fontFamily: 'monospace', fontSize: 11, color: '#94a3b8', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {v.url}
                      </td>
                      <td style={{ ...td, color: '#94a3b8' }}>{v.parameter ?? '—'}</td>
                      <td style={{ ...td, color: '#94a3b8' }}>{v.method}</td>
                      <td style={{ ...td, fontSize: 12, color: '#64748b', maxWidth: 250 }}>
                        {v.recommendation ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </main>
    </div>
  )
}
