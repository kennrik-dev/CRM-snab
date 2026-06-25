import type { DocsAggregate } from '../../api/support'

/** 4 квадрата ТТН/М-15/УПД/Серт. Зелёный = есть, красный (.no) = нет. */
const ENTRIES: { key: keyof DocsAggregate; label: string }[] = [
  { key: 'ttn', label: 'ТТН' },
  { key: 'm15', label: 'М-15' },
  { key: 'upd', label: 'УПД' },
  { key: 'sert', label: 'Серт' },
]

export function DocsSquares({ docs }: { docs: DocsAggregate }) {
  return (
    <span className="docsq">
      {ENTRIES.map((e) => (
        <span key={e.key} className={docs[e.key] ? '' : 'no'} title={e.label}>
          {e.label}
        </span>
      ))}
    </span>
  )
}
