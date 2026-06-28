import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало backend schemas/reports.py (Фаза 9.1). Слепок отчёта — generic-форма;
// money/date cells — предформатированные строки (BE).

export type ReportType = 'time' | 'sums' | 'late' | 'people'
export type ExportFormat = 'excel' | 'pdf' | 'csv'
export type ReportPeriodKey = 'month' | 'quarter' | 'year' | 'custom'

export type CellObj = {
  text?: string | null
  kind?: string | null      // claim|mono|text|stage|days|money|date|date-late|percent|note
  color?: string | null     // kind='stage': '--proc'
  level?: string | null     // kind='days': ''|'warn'|'bad'
  code?: string | null      // kind='claim': parent code
  title?: string | null     // kind='claim': title
}
export type Cell = string | CellObj

export type Column = { key: string; label: string; kind?: string | null; align?: string | null }
export type Section = {
  title?: string | null
  columns: Column[]
  rows: Cell[][]
  footer?: Cell[] | null
}
export type Kpi = { label: string; value: string; color?: string | null }
// BE serializes PeriodInfo.from_ with alias "from" → JSON key is "from".
export type PeriodInfo = { key: string; label: string; from?: string | null; to?: string | null }
export type ReportSnapshot = {
  type: string
  title: string
  period: PeriodInfo | null
  kpis: Kpi[]
  sections: Section[]
}
export type Filters = { mtr: string[]; supplier: string[]; author: string[] }
export type ReportFilters = {
  period?: ReportPeriodKey
  date_from?: string
  date_to?: string
  mtr?: string
  supplier?: string
  author?: string
}

export function getReport(type: ReportType, flt: ReportFilters): Promise<ReportSnapshot> {
  return apiFetch<ReportSnapshot>(`/reports/${type}${buildQuery(flt)}`)
}

export function getFilters(): Promise<Filters> {
  return apiFetch<Filters>('/reports')
}

// File download — bypasses apiFetch (which parses JSON); we need the binary blob.
export async function downloadReport(
  type: ReportType,
  flt: ReportFilters,
  format: ExportFormat,
): Promise<void> {
  const q = buildQuery({ ...flt, format })
  const res = await fetch(`/api/reports/${type}/export${q}`, { credentials: 'include' })
  if (!res.ok) {
    throw { status: res.status, body: await res.json().catch(() => null) }
  }
  const blob = await res.blob()
  const disp = res.headers.get('content-disposition') || ''
  const m = /filename="?([^"]+)"?/i.exec(disp)
  const filename =
    m?.[1] ||
    `otchety_${type}.${format === 'excel' ? 'xlsx' : format}`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
