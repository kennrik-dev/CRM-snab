import { apiFetch } from './client'

export type DictValue = {
  id: number
  kind: string
  value: string
  sort_order: number | null
}

export function listDict(kind: string): Promise<DictValue[]> {
  return apiFetch<DictValue[]>(`/dict/${kind}`)
}
