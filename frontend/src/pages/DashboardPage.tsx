import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

interface ScanItem {
  id: string
  target_url: string
  status: 'pending' | 'running' | 'paused' | 'finished' | 'failed'
  max_depth: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  vuln_count: number
}

const STATUS_LABEL: Record<ScanItem['status'], string> = {
  pending: 'Ожидание',
  running: 'Выполняется',
  paused: 'Приостановлен',
  finished: 'Завершён',
  failed: 'Ошибка',
}

const STATUS_COLOR: Record<ScanItem['status'], string> = {
  pending: '#64748b',
  running: '#2563eb',
  paused: '#d97706',
  finished: '#16a34a',
  failed: '#dc2626',
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [scans, setScans] = useState<ScanItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/scans').then(r => setScans(r.data)).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const active = scans.some(s => s.status === 'pending' || s.status === 'running')
    if (!active) return
    const id = setInterval(() => {
      api.get('/scans').then(r => setScans(r.data))
    }, 5000)
    return () => clearInterval(id)
  }, [scans])

  const btn: React.CSSProperties = {
    padding: '6px 14px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
  }
  const th: React.CSSProperties = {
    padding: '10px 12px', background: '#0f172a', fontSize: 13,
    color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid #1e293b',
  }
  const td: React.CSSProperties = { padding: '10px 12px', borderBottom: '1px solid #1e293b', fontSize: 14 }

  return (
    <div>
      <Navbar title="DAST Analyzer" />

      <main style={{ padding: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h2 style={{ margin: 0 }}>Сканирования</h2>
          <button style={{ ...btn, padding: '8px 20px', fontSize: 14 }} onClick={() => navigate('/scans/new')}>
            + Новое сканирование
          </button>
        </div>

        {loading ? (
          <p style={{ color: '#94a3b8' }}>Загрузка…</p>
        ) : scans.length === 0 ? (
          <div style={{ background: '#1e293b', borderRadius: 10, padding: 40, textAlign: 'center' }}>
            <p style={{ color: '#94a3b8', margin: 0 }}>Сканирований пока нет.</p>
            <button style={{ ...btn, marginTop: 16, padding: '8px 24px' }} onClick={() => navigate('/scans/new')}>
              Создать первое сканирование
            </button>
          </div>
        ) : (
          <div style={{ background: '#1e293b', borderRadius: 10, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={th}>Цель</th>
                  <th style={th}>Статус</th>
                  <th style={th}>Глубина</th>
                  <th style={th}>Уязвимостей</th>
                  <th style={th}>Создан</th>
                  <th style={th}></th>
                </tr>
              </thead>
              <tbody>
                {scans.map(scan => (
                  <tr key={scan.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/scans/${scan.id}`)}>
                    <td style={td}>
                      <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: 13 }}>
                        {scan.target_url.length > 50 ? scan.target_url.slice(0, 50) + '…' : scan.target_url}
                      </span>
                    </td>
                    <td style={td}>
                      <span style={{
                        padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                        background: STATUS_COLOR[scan.status] + '22', color: STATUS_COLOR[scan.status],
                        border: `1px solid ${STATUS_COLOR[scan.status]}44`,
                      }}>
                        {STATUS_LABEL[scan.status]}
                      </span>
                    </td>
                    <td style={{ ...td, color: '#94a3b8' }}>{scan.max_depth}</td>
                    <td style={{ ...td, color: scan.vuln_count > 0 ? '#f87171' : '#94a3b8' }}>{scan.vuln_count}</td>
                    <td style={{ ...td, color: '#94a3b8', fontSize: 12 }}>
                      {new Date(scan.created_at).toLocaleString('ru-RU')}
                    </td>
                    <td style={td}>
                      <button
                        style={{ ...btn, padding: '4px 12px', fontSize: 12 }}
                        onClick={e => { e.stopPropagation(); navigate(`/scans/${scan.id}`) }}
                      >
                        Подробнее
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
