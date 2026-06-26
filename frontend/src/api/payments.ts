import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало backend schemas/payments.py (Фаза 7.1). Деньги — int копейки,
// даты — ISO 'YYYY-MM-DD' строки (Optional).

// Whitelist sort-ключей бэкенда GET /payments (_SORT_KEYS в payments.py):
export type PaymentSort =
  | 'created_at'
  | 'upd'
  | 'request'
  | 'supplier'
  | 'contract'
  | 'zrds'
  | 'status'
  | 'srok'
  | 'amount'

export type UpdPositionOut = {
  id: number
  n: number | null
  name: string | null
  unit: string | null
  qty: number | null
  price: number | null
}

export type PaymentListItem = {
  id: number
  upd: string
  origin: string
  request_display: string | null
  supplier: string | null
  contract: string | null
  zrds: string | null
  delivery_n: number | null
  pay_status: string
  is_overdue: boolean
  srok: string | null
  pay_date: string | null
  amount: number | null
  created_at: string
}

export type PaginatedPayments = { items: PaymentListItem[]; total: number }

export type PaymentDeliveryOut = {
  n: number
  procedure_id: number
  parent_code: string | null
}

export type PaymentDetail = {
  id: number
  upd: string
  origin: string
  delivery_id: number | null
  request_label: string | null
  supplier: string | null
  contract: string | null
  zrds: string | null
  srok: string | null
  amount: number | null
  pay_status: string
  pay_date: string | null
  created_at: string
  positions: UpdPositionOut[]
  delivery: PaymentDeliveryOut | null
  is_overdue: boolean
}

export type PaymentCreate = {
  upd: string
  request_label?: string
  supplier?: string
  srok?: string
  amount?: number
  zrds?: string
  // LEAN (2026-06-26): positions editor deferred — manual amount is hand-entered
  // (docs/13 §8), so the FE never sends `positions`. BE still accepts it.
}

export type PaymentPatch = {
  srok?: string | null
  zrds?: string | null
  contract?: string | null
  supplier?: string | null
  amount?: number | null
}

export type SummaryMeters = { paid: number; await_: number; overdue: number; in_work: number }
export type SummaryBar = {
  paid: number
  await_: number
  delivered_no_upd: number
  contracted_no_delivery: number
}
export type PaymentsSummary = { meters: SummaryMeters; bar: SummaryBar }

// ---- Endpoints ------------------------------------------------------------

export function listPayments(params: {
  search?: string
  hide_paid?: boolean
  sort?: PaymentSort
  page?: number
  page_size?: number
} = {}): Promise<PaginatedPayments> {
  return apiFetch<PaginatedPayments>(`/payments${buildQuery(params)}`)
}

export function getPaymentsSummary(): Promise<PaymentsSummary> {
  return apiFetch<PaymentsSummary>('/payments/summary')
}

export function getPayment(id: number): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>(`/payments/${id}`)
}

export function createPayment(payload: PaymentCreate): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>('/payments', { method: 'POST', body: payload })
}

export function patchPayment(id: number, payload: PaymentPatch): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>(`/payments/${id}`, { method: 'PATCH', body: payload })
}

export function payPayment(id: number): Promise<PaymentDetail> {
  return apiFetch<PaymentDetail>(`/payments/${id}/pay`, { method: 'POST' })
}
