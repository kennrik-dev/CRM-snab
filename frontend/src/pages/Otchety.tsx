import { useState, type CSSProperties } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  getReport, getFilters, downloadReport,
  type ReportType, type ReportFilters, type ExportFormat, type Cell,
  type ReportSnapshot,
} from '../api/reports'
import { describeCell, periodOptionLabel } from '../lib/reportsView'
import { canView } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: 'time', label: 'Время на этапе / зависания' },
  { value: 'sums', label: 'Суммы по этапам и поставщикам' },
  { value: 'late', label: 'Просрочки: поставки и оплаты' },
  { value: 'people', label: 'Сводка по составителям/отделам' },
]
const PERIOD_KEYS = ['', 'month', 'quarter', 'year', 'custom'] as const
const FORMATS: { value: ExportFormat; label: string }[] = [
  { value: 'excel', label: 'Excel' },
  { value: 'pdf', label: 'PDF' },
  { value: 'csv', label: 'CSV' },
]

function CellView({ cell }: { cell: Cell }) {
  const d = describeCell(cell)
  if (d.tag !== undefined) {
    return (
      <>
        <span className="parent-tag">{d.tag}</span>
        {d.text}
      </>
    )
  }
  return <span className={d.className}>{d.text}</span>
}

function ReportTable({ section }: { section: ReportSnapshot['sections'][number] }) {
  return (
    <div>
      {section.title && (
        <div className="dsec-t" style={{ padding: '12px 16px 6px' }}>{section.title}</div>
      )}
      <div className="tbl-scroll">
        <table className="rtbl">
          <thead>
            <tr>
              {section.columns.map((c) => (
                <th key={c.key} className={c.align === 'right' ? 'r' : ''}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} className={section.columns[j]?.align === 'right' ? 'r' : ''}>
                    <CellView cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {section.footer && (
            <tfoot>
              <tr>
                {section.footer.map((cell, j) => (
                  <td key={j} className={section.columns[j]?.align === 'right' ? 'r' : ''}>
                    <CellView cell={cell} />
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

export function Otchety() {
  const { permissions } = useAuth()
  const [params, setParams] = useState<ReportFilters & { type: ReportType }>({ type: 'time' })

  const report = useQuery({
    queryKey: ['reports', params],
    queryFn: () => getReport(params.type, params),
  })
  const filters = useQuery({ queryKey: ['reports', 'filters'], queryFn: getFilters })

  if (!canView(permissions, 'reports')) return <Navigate to="/dashboard" replace />

  const set = (patch: Partial<typeof params>) => setParams((p) => ({ ...p, ...patch }))
  const snap = report.data
  const hasRows = (snap?.sections ?? []).some((s) => s.rows.length > 0 && !(s.rows.length === 1 && s.rows[0][0] && typeof s.rows[0][0] === 'object' && (s.rows[0][0] as { kind?: string }).kind === 'note'))

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>Отчёты</h1>
        <span className="desc">конструктор выгрузок для руководства</span>
        <span className="sp" />
      </div>

      <div className="rep-layout">
        <div className="rep-params">
          <h3>Параметры</h3>

          <div className="rep-group">
            <div className="rg-l">Тип отчёта</div>
            {REPORT_TYPES.map((t) => (
              <div
                key={t.value}
                className={`rep-opt${params.type === t.value ? ' on' : ''}`}
                onClick={() => set({ type: t.value })}
              >
                <i />
                {t.label}
              </div>
            ))}
          </div>

          <div className="rep-group">
            <div className="rg-l">Период</div>
            <select
              className="rep-sel"
              value={params.period ?? ''}
              onChange={(e) =>
                set({ period: (e.target.value || undefined) as ReportFilters['period'] })
              }
            >
              {PERIOD_KEYS.map((k) => (
                <option key={k} value={k}>{periodOptionLabel(k)}</option>
              ))}
            </select>
            {params.period === 'custom' && (
              <>
                <input
                  type="date" className="rep-sel"
                  value={params.date_from ?? ''}
                  onChange={(e) => set({ date_from: e.target.value || undefined })}
                />
                <input
                  type="date" className="rep-sel"
                  value={params.date_to ?? ''}
                  onChange={(e) => set({ date_to: e.target.value || undefined })}
                />
              </>
            )}
          </div>

          <div className="rep-group">
            <div className="rg-l">Фильтры</div>
            <select className="rep-sel" value={params.mtr ?? ''}
              onChange={(e) => set({ mtr: e.target.value || undefined })}>
              <option value="">Все типы МТР</option>
              {(filters.data?.mtr ?? []).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
            <select className="rep-sel" value={params.supplier ?? ''}
              onChange={(e) => set({ supplier: e.target.value || undefined })}>
              <option value="">Все поставщики</option>
              {(filters.data?.supplier ?? []).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
            <select className="rep-sel" value={params.author ?? ''}
              onChange={(e) => set({ author: e.target.value || undefined })}>
              <option value="">Все составители</option>
              {(filters.data?.author ?? []).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>

          <button className="rep-go" onClick={() => report.refetch()}>
            {report.isFetching ? 'Формирование…' : 'Сформировать'}
          </button>
        </div>

        <div className="rep-out">
          {report.isLoading ? (
            <div className="empty-state">Загрузка…</div>
          ) : report.isError ? (
            <div className="empty-state">
              Ошибка:{' '}
              {String(
                (report.error as { body?: { detail?: string } })?.body?.detail ?? report.error,
              )}
            </div>
          ) : !snap ? null : !hasRows ? (
            <div className="empty-state">По выбранным параметрам нет данных</div>
          ) : (
            <>
              <div className="rep-out-h">
                <h2>{snap.title}</h2>
                <span className="sp" />
                <div className="exp">
                  {FORMATS.map((f) => (
                    <button key={f.value} onClick={() => downloadReport(params.type, params, f.value)}>
                      ↧ {f.label}
                    </button>
                  ))}
                </div>
              </div>
              {snap.kpis.length > 0 && (
                <div className="rep-kpis">
                  {snap.kpis.map((k, i) => (
                    <div className="rep-kpi" key={i}>
                      <div className="l">{k.label}</div>
                      <div
                        className="v"
                        style={
                          k.color ? ({ color: `var(${k.color})` } as CSSProperties) : undefined
                        }
                      >
                        {k.value}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {snap.sections.map((s, i) => (
                <ReportTable key={i} section={s} />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
