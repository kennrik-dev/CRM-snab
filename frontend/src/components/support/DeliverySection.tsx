import { useState, type CSSProperties } from 'react'
import { Modal } from '../Modal'
import { DocToggle } from './DocToggle'
import { PayChip } from './PayChip'
import { EmptyState } from '../EmptyState'
import {
  createDelivery,
  deleteDelivery,
  patchDelivery,
  upsertUpd,
  type DeliveryOut,
} from '../../api/support'
import { money } from '../../lib/format'
import type { ProcedureDetail } from '../../api/procedures'

const DOC_FIELDS: { field: 'doc_ttn' | 'doc_m15' | 'doc_upd' | 'doc_sert'; label: string }[] = [
  { field: 'doc_ttn', label: 'ТТН' },
  { field: 'doc_m15', label: 'М-15' },
  { field: 'doc_upd', label: 'УПД' },
  { field: 'doc_sert', label: 'Серт' },
]

function lastErrorMessage(err: unknown): string {
  const e = err as { body?: { detail?: string } } | null
  return e?.body?.detail ?? 'Ошибка'
}

export function DeliverySection({
  proc,
  canEditThis,
  refresh,
}: {
  proc: ProcedureDetail
  canEditThis: boolean
  refresh: () => Promise<void>
}) {
  const [createOpen, setCreateOpen] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [err, setErr] = useState<string | null>(null)
  const [updDrafts, setUpdDrafts] = useState<Record<number, string>>({})

  const awaiting = proc.positions.filter((p) => p.delivery_id == null)
  const deliveries = [...proc.deliveries].sort((a, b) => a.n - b.n)

  async function run(fn: () => Promise<unknown>) {
    try {
      setErr(null)
      await fn()
      await refresh()
    } catch (e) {
      setErr(lastErrorMessage(e))
    }
  }

  const createMut = () =>
    run(async () => {
      if (selected.size === 0) return
      await createDelivery(proc.id, { positions: [...selected] })
      setCreateOpen(false)
      setSelected(new Set())
    })
  const toggleDoc = (d: DeliveryOut, field: 'doc_ttn' | 'doc_m15' | 'doc_upd' | 'doc_sert') =>
    run(() => patchDelivery(d.id, { [field]: d[field] ? 0 : 1 }))
  const markDone = (d: DeliveryOut) => run(() => patchDelivery(d.id, { status: 'done' }))
  const disband = (d: DeliveryOut) => run(() => deleteDelivery(d.id))
  const submitUpd = (d: DeliveryOut, value: string) =>
    run(async () => {
      if (!value.trim()) return
      await upsertUpd(d.id, { upd: value.trim() })
      setUpdDrafts((m) => { const n = { ...m }; delete n[d.id]; return n })
    })

  return (
    <div className="block reg" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
      <div className="block-h">
        <span className="btitle">Поставки ({deliveries.length})</span>
        <span className="sp" style={{ flex: 1 }} />
        {canEditThis && (
          <button
            className="btn primary"
            disabled={awaiting.length === 0}
            onClick={() => { setSelected(new Set()); setCreateOpen(true) }}
            title={awaiting.length === 0 ? 'Нет позиций в ожидании' : 'Создать поставку'}
          >
            + Создать поставку
          </button>
        )}
        {err && <span style={{ color: 'var(--late)', fontSize: 12 }}>{err}</span>}
      </div>

      {deliveries.length === 0 ? (
        <div style={{ padding: 12 }}><EmptyState title="Поставок нет" hint="Создайте поставку из позиций «ожидают отгрузки»." /></div>
      ) : (
        deliveries.map((d) => {
          const dPositions = proc.positions.filter((p) => p.delivery_id === d.id)
          const updValue = updDrafts[d.id] ?? d.upd?.upd ?? ''
          const canDisband = canEditThis && d.status === 'transit' && !d.upd
          const canMarkDone = canEditThis && d.status === 'transit'
          return (
            <div key={d.id} style={{ borderTop: '1px solid var(--line)', padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <strong>Поставка №{d.n}</strong>
                <span className={`chip ${d.status === 'done' ? 'ok' : 'proc'} mini`}>
                  {d.status === 'done' ? 'Получена' : 'В пути'}
                </span>
                {d.date && <span style={{ color: 'var(--muted)', fontSize: 12 }}>от {d.date}</span>}
                {d.eta && d.status === 'transit' && <span style={{ color: 'var(--muted)', fontSize: 12 }}>ETA {d.eta}</span>}
                <span className="sp" style={{ flex: 1 }} />
                {canMarkDone && <button className="btn" onClick={() => markDone(d)}>Отметить получение</button>}
                {canDisband && <button className="btn" onClick={() => disband(d)}>Расформировать</button>}
              </div>

              <table className="postbl" style={{ marginBottom: 8 }}>
                <thead>
                  <tr><th>Наименование</th><th>Кол-во</th><th>Ед.</th><th>Сумма</th></tr>
                </thead>
                <tbody>
                  {dPositions.map((p) => (
                    <tr key={p.id}>
                      <td>{p.name}</td><td>{p.qty}</td><td>{p.unit ?? '—'}</td>
                      <td>{money(p.price != null ? Math.round(p.qty * p.price) : null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                {DOC_FIELDS.map((df) => (
                  <DocToggle
                    key={df.field}
                    label={df.label}
                    on={!!d[df.field]}
                    disabled={!canEditThis}
                    onClick={() => toggleDoc(d, df.field)}
                  />
                ))}
                <span style={{ flex: 1 }} />
                {canEditThis ? (
                  <>
                    <input
                      placeholder="№ УПД"
                      value={updValue}
                      onChange={(e) => setUpdDrafts((m) => ({ ...m, [d.id]: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') submitUpd(d, updValue) }}
                      style={{ border: '1px solid var(--line)', borderRadius: 5, padding: '3px 8px', fontFamily: 'inherit', fontSize: 12, width: 150 }}
                    />
                    <button className="btn" disabled={!updValue.trim() || updValue === (d.upd?.upd ?? '')} onClick={() => submitUpd(d, updValue)}>
                      Ввести УПД
                    </button>
                  </>
                ) : (
                  d.upd?.upd && <span style={{ fontSize: 12 }}>УПД: {d.upd.upd}</span>
                )}
                <PayChip payStatus={d.upd?.pay_status} />
              </div>
            </div>
          )
        })
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Создать поставку"
        width={620}
        footer={
          <>
            <button className="btn" onClick={() => setCreateOpen(false)}>Отмена</button>
            <button className="btn primary" disabled={selected.size === 0} onClick={createMut}>
              Создать ({selected.size})
            </button>
          </>
        }
      >
        {awaiting.length === 0 ? (
          <EmptyState title="Нет позиций в ожидании отгрузки" />
        ) : (
          <table className="postbl">
            <thead>
              <tr><th></th><th>Наименование</th><th>Кол-во</th><th>Ед.</th></tr>
            </thead>
            <tbody>
              {awaiting.map((p) => {
                const checked = selected.has(p.id)
                return (
                  <tr key={p.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setSelected((prev) => {
                            const n = new Set(prev)
                            if (checked) n.delete(p.id); else n.add(p.id)
                            return n
                          })
                        }
                      />
                    </td>
                    <td>{p.name}</td><td>{p.qty}</td><td>{p.unit ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Modal>
    </div>
  )
}
