import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import Navbar from '../components/Navbar'

interface Wordlist {
  id: string
  name: string
  size_bytes: number
  is_builtin: boolean
  created_at: string
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

export default function WordlistsPage() {
  const [wordlists, setWordlists] = useState<Wordlist[]>([])
  const [loading, setLoading] = useState(true)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadErr, setUploadErr] = useState('')
  const [deleteErr, setDeleteErr] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function load() {
    try {
      const { data } = await api.get('/wordlists')
      setWordlists(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadErr('')
    setUploadLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      await api.post('/wordlists', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      await load()
    } catch (err: any) {
      const status = err.response?.status
      if (status === 415) setUploadErr('Неверный тип файла. Разрешены только .txt файлы.')
      else if (status === 413) setUploadErr('Файл слишком большой.')
      else setUploadErr(err.response?.data?.detail ?? 'Ошибка загрузки')
    } finally {
      setUploadLoading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleDelete(id: string) {
    setDeleteErr('')
    try {
      await api.delete(`/wordlists/${id}`)
      setWordlists(prev => prev.filter(w => w.id !== id))
    } catch (err: any) {
      setDeleteErr(err.response?.data?.detail ?? 'Ошибка удаления')
    }
  }

  const card: React.CSSProperties = {
    background: '#1e293b', borderRadius: 10, padding: 24, marginBottom: 20,
  }
  const btn: React.CSSProperties = {
    minHeight: 44, minWidth: 44,
    padding: '7px 16px', background: '#1e40af', color: '#fff',
    border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer',
  }

  return (
    <div>
      <Navbar title="Словари нагрузок" backTo="/dashboard" backLabel="← Главная" />

      <main style={{ padding: 32, maxWidth: 800, margin: '0 auto' }}>

        {/* Upload */}
        <div style={card}>
          <h3 style={{ margin: '0 0 12px', fontSize: 15 }}>Загрузить словарь</h3>
          <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 16 }}>
            Загрузите текстовый файл (.txt) с полезными нагрузками — по одной на строку.
            Строки, начинающиеся с «#», считаются комментариями и пропускаются.
            Рекомендуемый размер: до 10 ГБ.
          </p>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button
              style={btn}
              onClick={() => fileRef.current?.click()}
              disabled={uploadLoading}
            >
              {uploadLoading ? 'Загрузка…' : '+ Выбрать файл'}
            </button>
            <span style={{ fontSize: 12, color: '#475569' }}>Только .txt файлы</span>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,text/plain"
            style={{ display: 'none' }}
            onChange={handleUpload}
          />
          {uploadErr && <p style={{ color: '#f87171', marginTop: 10, fontSize: 13 }}>{uploadErr}</p>}
        </div>

        {/* List */}
        <div style={card}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>Словари</h3>
          {loading ? (
            <p style={{ color: '#94a3b8' }}>Загрузка…</p>
          ) : wordlists.length === 0 ? (
            <p style={{ color: '#94a3b8' }}>Нет загруженных словарей.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Название', 'Размер', 'Дата', ''].map(h => (
                    <th key={h} style={{
                      padding: '8px 12px', background: '#0f172a', fontSize: 12,
                      color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid #1e293b',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {wordlists.map(w => (
                  <tr key={w.id}>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid #0f172a', fontSize: 13 }}>
                      {w.name}
                      {w.is_builtin && (
                        <span style={{
                          marginLeft: 8, padding: '1px 6px', borderRadius: 8, fontSize: 10,
                          background: '#1e40af22', color: '#60a5fa', border: '1px solid #1e40af44',
                        }}>встроенный</span>
                      )}
                    </td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid #0f172a', fontSize: 13, color: '#94a3b8' }}>
                      {fmtSize(w.size_bytes)}
                    </td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid #0f172a', fontSize: 12, color: '#64748b' }}>
                      {new Date(w.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td style={{ padding: '10px 12px', borderBottom: '1px solid #0f172a', textAlign: 'right' }}>
                      {!w.is_builtin && (
                        <button
                          style={{ ...btn, background: '#7f1d1d', padding: '4px 12px', fontSize: 12 }}
                          onClick={() => handleDelete(w.id)}
                        >
                          Удалить
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {deleteErr && <p style={{ color: '#f87171', marginTop: 10, fontSize: 13 }}>{deleteErr}</p>}
        </div>

      </main>
    </div>
  )
}
