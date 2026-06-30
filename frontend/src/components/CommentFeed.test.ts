import { describe, it, expect } from 'vitest'
import { canDeleteComment, commentPlaceholder } from './CommentFeed'
import type { Comment } from '../api/comments'

function c(over: Partial<Comment> = {}): Comment {
  return {
    id: 1,
    target_kind: 'parent',
    target_id: 1,
    author_id: 7,
    author: 'Иванов',
    role: 'Закупки',
    text: 'x',
    created_at: '2026-06-30 10:00:00',
    ...over,
  }
}

describe('canDeleteComment', () => {
  it('author can delete own', () =>
    expect(canDeleteComment({ id: 7, global_role: null }, c())).toBe(true))
  it('non-author non-admin cannot', () =>
    expect(canDeleteComment({ id: 8, global_role: null }, c())).toBe(false))
  it('admin can delete any', () =>
    expect(canDeleteComment({ id: 99, global_role: 'Админ' }, c())).toBe(true))
  it('null user cannot', () => expect(canDeleteComment(null, c())).toBe(false))
  it('comment with null author_id: only admin', () => {
    expect(canDeleteComment({ id: 7, global_role: null }, c({ author_id: null }))).toBe(false)
    expect(canDeleteComment({ id: 7, global_role: 'Админ' }, c({ author_id: null }))).toBe(true)
  })
})

describe('commentPlaceholder', () => {
  it('stamps the role', () => expect(commentPlaceholder('Закупки')).toContain('Закупки'))
  it('falls back to dash for null', () => expect(commentPlaceholder(null)).toContain('—'))
})
