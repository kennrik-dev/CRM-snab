import { apiFetch } from './client'
import { buildQuery } from './support'

// Зеркало /comments (Phase 10 B2). snake_case wire-типы; money/dates — как на сервере.

export type CommentTargetKind = 'parent' | 'tender' | 'procedure'

export type Comment = {
  id: number
  target_kind: string
  target_id: number
  author_id: number | null
  author: string | null
  role: string | null
  text: string
  created_at: string
}
export type CommentList = { items: Comment[]; total: number }
export type CommentCreate = { target_kind: CommentTargetKind; target_id: number; text: string }

export function listComments(
  target_kind: string,
  target_id: number,
  page?: number,
): Promise<CommentList> {
  return apiFetch<CommentList>(`/comments${buildQuery({ target_kind, target_id, page })}`)
}

export function createComment(payload: CommentCreate): Promise<Comment> {
  return apiFetch<Comment>('/comments', { method: 'POST', body: payload })
}

export function deleteComment(id: number): Promise<void> {
  return apiFetch<void>(`/comments/${id}`, { method: 'DELETE' })
}
