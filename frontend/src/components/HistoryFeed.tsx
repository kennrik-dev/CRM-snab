import { useQuery } from '@tanstack/react-query'
import { listHistory } from '../api/history'
import { relTime } from '../lib/dashView'

/** Actor fallback for a null/blank audit actor. Pure; unit-tested. (BE already sends 'Система'.) */
export function actorLabel(actor: string | null | undefined): string {
  return actor && actor.trim() ? actor : 'Система'
}

export function HistoryFeed({
  entityKind,
  entityId,
}: {
  entityKind: string
  entityId: number
}) {
  const q = useQuery({
    queryKey: ['history', entityKind, entityId],
    queryFn: () => listHistory(entityKind, entityId),
    enabled: Number.isFinite(entityId) && entityId > 0,
  })
  const items = q.data?.items ?? []
  return (
    <div className="history" style={{ maxHeight: 240, overflowY: 'auto' }}>
      {items.length === 0 ? (
        <div className="fitem" style={{ color: 'var(--faint)' }}>
          Журнал действий пуст.
        </div>
      ) : (
        items.map((e) => (
          <div className="fitem" key={e.id}>
            <span className="ft2">{relTime(e.created_at)}</span>
            <div>
              <b>{actorLabel(e.actor)}</b> <span>{e.action}</span>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
