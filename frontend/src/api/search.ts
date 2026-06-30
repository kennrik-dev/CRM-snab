import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало GET /search (Phase 10 B1). 5 групп; procedures содержат block для роутинга.

export type SearchParent = { id: number; code: string; title: string }
export type SearchProcedure = {
  id: number
  proc: string | null
  supplier: string | null
  tender_id: number
  block: string
}
export type SearchSupplier = { id: number; name: string; proc_count: number }
export type SearchTender = { id: number; num: string; parent_id: number; parent_code: string }
export type SearchPayment = { id: number; upd: string; supplier: string | null }
export type SearchResult = {
  parents: SearchParent[]
  procedures: SearchProcedure[]
  suppliers: SearchSupplier[]
  tenders: SearchTender[]
  payments: SearchPayment[]
}

export function getSearch(q: string, limit?: number): Promise<SearchResult> {
  return apiFetch<SearchResult>(`/search${buildQuery({ q, limit })}`)
}
