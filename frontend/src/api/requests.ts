import { apiFetch } from './client'

// ---- Types ----------------------------------------------------------------

export type RequestStatus = 'awaiting' | 'cancelled'
export type RequestSort = 'created_at' | 'code' | 'title'

export type RequestListItem = {
  id: number
  code: string
  title: string
  mtr: string | null
  srok: string | null
  zagruzka: string
  sostavitel: string
  status: RequestStatus
  created_at: string
  position_count: number
}

export type PaginatedRequests = {
  items: RequestListItem[]
  total: number
}

export type RequestPosition = {
  id: number
  parent_id: number
  name: string
  qty: number
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
}

export type ProcedureOut = {
  id: number
  tender_id: number
  proc: string | null
  supplier: string | null
  block: string
  status_zakup: string | null
  status_postavki: string | null
  status_sdelki: string | null
}

export type TenderOut = {
  id: number
  parent_id: number
  num: string | null
  procedures: ProcedureOut[]
}

export type RequestOut = {
  id: number
  code: string
  title: string
  mtr: string | null
  srok: string | null
  zagruzka: string
  sostavitel: string
  created_by: number | null
  dept: string | null
  status: RequestStatus
  created_at: string
  positions: RequestPosition[]
  tenders: TenderOut[]
}

export type RequestPositionInput = {
  name: string
  qty: number
  unit?: string | null
  gost_tu?: string | null
  doc_code?: string | null
}

export type RequestCreate = {
  code: string
  title: string
  mtr?: string | null
  srok?: string | null
  dept?: string | null
  positions: RequestPositionInput[]
}

export type RequestPatch = {
  title?: string
  mtr?: string | null
  srok?: string | null
  dept?: string | null
}

export type TakeToWorkResponse = {
  tender_id: number
  procedure_id: number
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

export function listRequests(params: {
  include_archived?: boolean
  status?: RequestStatus
  search?: string
  sort?: RequestSort
  page?: number
  page_size?: number
} = {}): Promise<PaginatedRequests> {
  return apiFetch<PaginatedRequests>(`/requests${buildQuery(params)}`)
}

export function getRequest(id: number): Promise<RequestOut> {
  return apiFetch<RequestOut>(`/requests/${id}`)
}

export function createRequest(payload: RequestCreate): Promise<RequestOut> {
  return apiFetch<RequestOut>('/requests', { method: 'POST', body: payload })
}

export function patchRequest(
  id: number,
  payload: RequestPatch,
): Promise<RequestOut> {
  return apiFetch<RequestOut>(`/requests/${id}`, {
    method: 'PATCH',
    body: payload,
  })
}

export function cancelRequest(id: number): Promise<RequestOut> {
  return apiFetch<RequestOut>(`/requests/${id}/cancel`, { method: 'POST' })
}

export function uncancelRequest(id: number): Promise<RequestOut> {
  return apiFetch<RequestOut>(`/requests/${id}/uncancel`, { method: 'POST' })
}

export function duplicateRequest(id: number, code: string): Promise<RequestOut> {
  return apiFetch<RequestOut>(`/requests/${id}/duplicate`, {
    method: 'POST',
    body: { code },
  })
}

export function takeToWork(id: number): Promise<TakeToWorkResponse> {
  return apiFetch<TakeToWorkResponse>(`/requests/${id}/take-to-work`, {
    method: 'POST',
  })
}

export function listPositions(requestId: number): Promise<RequestPosition[]> {
  return apiFetch<RequestPosition[]>(`/requests/${requestId}/positions`)
}

export function addPositions(
  requestId: number,
  positions: RequestPositionInput[],
): Promise<RequestPosition[]> {
  return apiFetch<RequestPosition[]>(`/requests/${requestId}/positions`, {
    method: 'POST',
    body: positions,
  })
}

export function patchPosition(
  requestId: number,
  posId: number,
  payload: Partial<RequestPosition>,
): Promise<RequestPosition> {
  return apiFetch<RequestPosition>(
    `/requests/${requestId}/positions/${posId}`,
    { method: 'PATCH', body: payload },
  )
}

export function deletePosition(
  requestId: number,
  posId: number,
): Promise<void> {
  return apiFetch<void>(`/requests/${requestId}/positions/${posId}`, {
    method: 'DELETE',
  })
}
