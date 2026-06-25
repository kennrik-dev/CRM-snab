import { progressState } from '../../lib/supportView'

/** Прогресс поставки: `.prog` + `.bar i` (ширина %), `.done` когда всё получено. */
export function Progress({ delivered, total }: { delivered: number; total: number }) {
  const { pct, done } = progressState(delivered, total)
  return (
    <div className={`prog${done ? ' done' : ''}`}>
      <div className="bar">
        <i style={{ width: `${pct}%` }} />
      </div>
      <span className="pn">
        <b>{delivered}</b>/{total}
      </span>
    </div>
  )
}
