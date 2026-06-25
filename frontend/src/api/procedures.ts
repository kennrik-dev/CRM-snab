import { apiFetch } from './client'
import type { DeliveryOut } from './support'

// ---- Types ----------------------------------------------------------------
// Mirrors backend schemas/procedures.py EXACTLY (see plan 5.1/5.2):
//   - proc / supplier / fio_zakupshchik / mtr / pub_start / pub_end are
//     nullable; status_zakup is nullable; price is INTEGER kopecks.
// The 10 sort keys whitelist the backend accepts (plan §123):
//   created_at | code | num | proc | supplier | status | mtr | zagruzka |
//   pub_start | pub_end

export type ProcedureSort =
  | 'created_at'
  | 'code'
  | 'num'
  | 'proc'
  | 'supplier'
  | 'status'
  | 'mtr'
  | 'zagruzka'
  | 'pub_start'
  | 'pub_end'

export type ProcedureListItem = {
  id: number
  proc: string | null
  tender_num: string | null
  code: string
  title: string
  mtr: string | null
  supplier: string | null
  fio_zakupshchik: string | null
  pub_start: string | null
  pub_end: string | null
  zagruzka: string
  position_count: number
  status_zakup: string | null
  created_at: string
}

export type PaginatedProcedures = {
  items: ProcedureListItem[]
  total: number
}

export type ProcedurePosition = {
  id: number
  procedure_id: number
  source_id: number | null
  name: string
  qty: number
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
  price: number | null // INTEGER kopecks
  delivery_id: number | null // NULL = «ожидает отгрузки» (Фаза 6.2)
}

export type ProcedureDetail = {
  id: number
  proc: string | null
  tender_id: number
  tender_num: string | null
  parent_id: number
  code: string
  title: string
  mtr: string | null
  supplier: string | null
  fio_zakupshchik: string | null
  pub_start: string | null
  pub_end: string | null
  zagruzka: string
  block: string
  status_zakup: string | null
  // Б2 (Сопровождение, Фаза 6.2):
  contract: string | null
  fio_dogovornik: string | null
  contract_sum: number | null
  status_sdelki: string | null
  status_postavki: string | null
  srok_dd: string | null
  plan_date: string | null
  fakt_date: string | null
  created_at: string
  positions: ProcedurePosition[]
  deliveries: DeliveryOut[]
}

export type ProcedurePatch = {
  proc?: string | null
  tender_num?: string | null
  supplier?: string | null
  fio_zakupshchik?: string | null
  mtr?: string | null
  pub_start?: string | null
  pub_end?: string | null
  status_zakup?: string | null
  // Б2 (Сопровождение):
  contract?: string | null
  fio_dogovornik?: string | null
  contract_sum?: number | null
  status_sdelki?: string | null
  status_postavki?: string | null
  srok_dd?: string | null
  plan_date?: string | null
  fakt_date?: string | null
}

export type SplitItem = {
  source_position_id: number
  qty: number
}

export type SplitPayload = {
  positions: SplitItem[]
  supplier?: string | null
  proc?: string | null
  mtr?: string | null
}

export type ProcedurePositionInput = {
  name: string
  qty: number
  unit?: string | null
  gost_tu?: string | null
  doc_code?: string | null
  price?: number | null
  source_id?: number | null
}

export type ProcedurePositionPatch = {
  name?: string | null
  qty?: number | null
  unit?: string | null
  gost_tu?: string | null
  doc_code?: string | null
  price?: number | null
}

// ---- Helpers --------------------------------------------------------------

function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

// ---- Endpoints ------------------------------------------------------------

export function listProcurements(params: {
  include_archived?: boolean
  search?: string
  sort?: ProcedureSort
  page?: number
  page_size?: number
} = {}): Promise<PaginatedProcedures> {
  return apiFetch<PaginatedProcedures>(`/procurement${buildQuery(params)}`)
}

export function getProcedure(id: number): Promise<ProcedureDetail> {
  return apiFetch<ProcedureDetail>(`/procedures/${id}`)
}

export function patchProcedure(
  id: number,
  payload: ProcedurePatch,
): Promise<ProcedureDetail> {
  return apiFetch<ProcedureDetail>(`/procedures/${id}`, {
    method: 'PATCH',
    body: payload,
  })
}

export function splitProcedure(
  id: number,
  payload: SplitPayload,
): Promise<ProcedureDetail> {
  return apiFetch<ProcedureDetail>(`/procedures/${id}/split`, {
    method: 'POST',
    body: payload,
  })
}

export function cancelProcedure(id: number): Promise<ProcedureDetail> {
  return apiFetch<ProcedureDetail>(`/procedures/${id}/cancel`, {
    method: 'POST',
  })
}

export function uncancelProcedure(id: number): Promise<ProcedureDetail> {
  return apiFetch<ProcedureDetail>(`/procedures/${id}/uncancel`, {
    method: 'POST',
  })
}

export function toSupport(id: number): Promise<ProcedureDetail> {
  return apiFetch<ProcedureDetail>(`/procedures/${id}/to-support`, {
    method: 'POST',
  })
}

export function listProcedurePositions(
  id: number,
): Promise<ProcedurePosition[]> {
  return apiFetch<ProcedurePosition[]>(`/procedures/${id}/positions`)
}

export function addProcedurePositions(
  id: number,
  positions: ProcedurePositionInput[],
): Promise<ProcedurePosition[]> {
  return apiFetch<ProcedurePosition[]>(`/procedures/${id}/positions`, {
    method: 'POST',
    body: positions,
  })
}

export function patchProcedurePosition(
  id: number,
  posId: number,
  payload: ProcedurePositionPatch,
): Promise<ProcedurePosition> {
  return apiFetch<ProcedurePosition>(
    `/procedures/${id}/positions/${posId}`,
    { method: 'PATCH', body: payload },
  )
}

export function deleteProcedurePosition(
  id: number,
  posId: number,
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(
    `/procedures/${id}/positions/${posId}`,
    { method: 'DELETE' },
  )
}
