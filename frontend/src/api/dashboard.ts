import { apiFetch } from './client'

// Зеркало backend schemas/dashboard.py (Фаза 8.1). Деньги — int копейки,
// даты — ISO строки (Optional). Метры: amount — коп. (FE форматирует money()).

export type Target = { kind: string; id: number }

export type SegBar = { on: number; total: number }

export type Meter = {
  key: string
  label: string
  value: number
  unit: string | null
  sub: string | null // text detail (e.g. "34 / 39 поставок")
  amount: number | null // kopecks; rendered via money() when sub is null
  seg: SegBar
  color: string // bare token, e.g. 'proc' → rendered as var(--proc)
}

export type FlowStage = {
  key: string
  label: string
  count: number
  sub: string | null
  route: string
  color: string
}

export type AttentionItem = {
  id_label: string
  severity: string // 'error' | 'warning'
  text: string
  target: Target
}

export type FeedItem = {
  actor: string
  action_label: string
  entity_display: string | null
  target: Target | null
  created_at: string
}

export type AwaitingRow = {
  id: number
  code: string
  title: string
  mtr: string | null
  srok: string | null
  position_count: number
  status: string
}

export type ProcurementRow = {
  id: number
  code: string
  title: string
  num: string | null
  supplier: string | null
  position_count: number
  status_zakup: string | null
}

export type SupportRow = {
  id: number
  code: string
  title: string
  num: string | null
  supplier: string | null
  contract_sum: number | null
  status_postavki: string | null
  overdue_pct: number
  delivered: number
  total: number
}

export type CompactTable<R> = { total: number; items: R[] }

export type DashboardTables = {
  awaiting: CompactTable<AwaitingRow>
  procurement: CompactTable<ProcurementRow>
  support: CompactTable<SupportRow>
}

export type DashboardData = {
  meters: Meter[]
  flow: FlowStage[]
  attention: AttentionItem[]
  feed: FeedItem[]
  tables: DashboardTables
}

// ---- Endpoint ------------------------------------------------------------

export function getDashboard(): Promise<DashboardData> {
  return apiFetch<DashboardData>('/dashboard')
}
