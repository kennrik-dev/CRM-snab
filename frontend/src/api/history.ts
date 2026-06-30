import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало GET /history (Phase 10 B3). actor = User.full_name | 'Система' (BE).

export type AuditEntry = { id: number; action: string; actor: string; created_at: string }
export type HistoryList = { items: AuditEntry[]; total: number }

export function listHistory(
  entity_kind: string,
  entity_id: number,
  page?: number,
): Promise<HistoryList> {
  return apiFetch<HistoryList>(`/history${buildQuery({ entity_kind, entity_id, page })}`)
}
