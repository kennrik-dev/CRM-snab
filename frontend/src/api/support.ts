import { apiFetch } from './client'

// Зеркало backend schemas/deliveries.py (Фаза 6.2) + SupportListItem (support.py).

// ---- Helpers --------------------------------------------------------------

/** Сериализует params в querystring, пропуская undefined/null/''. Pure. */
export function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

// ---- Types ----------------------------------------------------------------

export const STATUS_POSTAVKI = [
  'Новая',
  'В производстве',
  'В поставке',
  'Частично поставлено',
  'Поставлено',
  'Отменена',
] as const
export type StatusPostavki = (typeof STATUS_POSTAVKI)[number]

// Whitelist sort-ключей бэкенда GET /support (_SORT_KEYS в support.py):
export type SupportSort =
  | 'created_at'
  | 'code'
  | 'proc'
  | 'supplier'
  | 'contract_sum'
  | 'status_postavki'
  | 'status_sdelki'
  | 'srok_dd'
  | 'plan_date'
  | 'fakt_date'

export type DocsAggregate = { ttn: boolean; m15: boolean; upd: boolean; sert: boolean }

export type SupportListItem = {
  id: number
  proc: string | null
  tender_num: string | null
  code: string
  title: string
  mtr: string | null
  supplier: string | null
  contract: string | null
  contract_sum: number | null
  status_sdelki: string | null
  status_postavki: string | null
  srok_dd: string | null
  plan_date: string | null
  fakt_date: string | null
  is_overdue: boolean
  overdue_pct: number
  docs: DocsAggregate
  progress_delivered: number
  progress_total: number
  created_at: string
}

export type PaginatedSupport = { items: SupportListItem[]; total: number }

export type DeliveryStatus = 'transit' | 'done'

export type UpdOut = { upd: string; pay_status: string } | null

export type DeliveryOut = {
  id: number
  n: number
  status: DeliveryStatus
  date: string | null
  eta: string | null
  doc_ttn: number // 0 | 1
  doc_m15: number
  doc_upd: number
  doc_sert: number
  upd: UpdOut
}

export type DeliveryCreate = { positions: number[] } // ≥1 (бэкенд 422 на пустой)

export type DeliveryPatch = {
  status?: DeliveryStatus // 'done' (transit→done one-way)
  date?: string | null
  eta?: string | null
  doc_ttn?: number
  doc_m15?: number
  doc_upd?: number
  doc_sert?: number
}

export type UpdIn = { upd: string }

// ---- Endpoints ------------------------------------------------------------

export function listSupport(params: {
  include_archived?: boolean
  search?: string
  sort?: SupportSort
  page?: number
  page_size?: number
} = {}): Promise<PaginatedSupport> {
  return apiFetch<PaginatedSupport>(`/support${buildQuery(params)}`)
}

export function createDelivery(
  procedureId: number,
  payload: DeliveryCreate,
): Promise<DeliveryOut> {
  return apiFetch<DeliveryOut>(`/procedures/${procedureId}/deliveries`, {
    method: 'POST',
    body: payload,
  })
}

export function deleteDelivery(id: number): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/deliveries/${id}`, { method: 'DELETE' })
}

export function patchDelivery(id: number, payload: DeliveryPatch): Promise<DeliveryOut> {
  return apiFetch<DeliveryOut>(`/deliveries/${id}`, { method: 'PATCH', body: payload })
}

export function upsertUpd(deliveryId: number, payload: UpdIn): Promise<UpdOut> {
  return apiFetch<UpdOut>(`/deliveries/${deliveryId}/upd`, { method: 'POST', body: payload })
}
