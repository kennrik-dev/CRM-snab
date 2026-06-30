import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listComments, createComment, deleteComment, type Comment, type CommentTargetKind } from '../api/comments'
import { useAuth } from '../auth/AuthContext'
import { relTime } from '../lib/dashView'
import { initials, roleLabel } from './CommandBar'

type Me = { id: number; global_role: string | null; full_name?: string } | null

/** Delete allowed for the author OR Админ. Pure; unit-tested. */
export function canDeleteComment(me: Me, c: Comment): boolean {
  if (!me) return false
  return c.author_id === me.id || me.global_role === 'Админ'
}

/** Role-stamped input placeholder (canon). Pure; unit-tested. */
export function commentPlaceholder(role: string | null): string {
  return `Комментарий по заявке от лица «${role ?? '—'}»…`
}

export function CommentFeed({
  targetKind,
  targetId,
}: {
  targetKind: CommentTargetKind
  targetId: number
}) {
  const qc = useQueryClient()
  const { me } = useAuth()
  const [text, setText] = useState('')
  const enabled = Number.isFinite(targetId) && targetId > 0

  const q = useQuery({
    queryKey: ['comments', targetKind, targetId],
    queryFn: () => listComments(targetKind, targetId),
    enabled,
  })

  const addMut = useMutation({
    mutationFn: (t: string) =>
      createComment({ target_kind: targetKind, target_id: targetId, text: t }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments', targetKind, targetId] })
      qc.invalidateQueries({ queryKey: ['history', targetKind, targetId] })
      setText('')
    },
  })

  const delMut = useMutation({
    mutationFn: (id: number) => deleteComment(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments', targetKind, targetId] })
      qc.invalidateQueries({ queryKey: ['history', targetKind, targetId] })
    },
  })

  const items = q.data?.items ?? []
  const submit = () => {
    const t = text.trim()
    if (t && !addMut.isPending) addMut.mutate(t)
  }

  return (
    <div className="comments">
      {items.length === 0 ? (
        <div className="cmt-empty">Пока нет комментариев. Будьте первым.</div>
      ) : (
        items.map((cm) => (
          <div className="cmt" key={cm.id}>
            <div className={`cmt-av${cm.author_id === me?.id ? ' me' : ''}`}>
              {initials(cm.author ?? '?')}
            </div>
            <div className="cmt-b">
              <div className="cmt-h">
                <b>{cm.author ?? '—'}</b>
                {cm.role && <span className="cmt-r">{cm.role}</span>}
                <span className="cmt-t">{relTime(cm.created_at)}</span>
              </div>
              <div className="cmt-x">{cm.text}</div>
            </div>
            {canDeleteComment(me, cm) && (
              <button
                type="button"
                title="Удалить комментарий"
                onClick={() => delMut.mutate(cm.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--faint)',
                  cursor: 'pointer',
                  fontSize: 16,
                  padding: '0 4px',
                }}
              >
                ×
              </button>
            )}
          </div>
        ))
      )}
      <div className="cmt-new">
        <div className="cmt-av me">{me ? initials(me.full_name) : '—'}</div>
        <textarea
          placeholder={commentPlaceholder(me ? roleLabel(me) : null)}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit()
          }}
          rows={2}
        />
        <button
          type="button"
          className="btn primary"
          disabled={!text.trim() || addMut.isPending}
          onClick={submit}
        >
          {addMut.isPending ? 'Отправка…' : 'Отправить'}
        </button>
      </div>
    </div>
  )
}
