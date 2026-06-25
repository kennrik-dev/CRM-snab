import type { DocsAggregate } from '../../api/support'

/** 4 квадрата по одной букве Т/М/У/С (tooltip — полное название).
 * Зелёный = документ есть, красный (.no) = нет. */
const ENTRIES: { key: keyof DocsAggregate; label: string; title: string }[] = [
  { key: 'ttn', label: 'Т', title: 'ТТН' },
  { key: 'm15', label: 'М', title: 'М-15' },
  { key: 'upd', label: 'У', title: 'УПД' },
  { key: 'sert', label: 'С', title: 'Сертификат' },
]

export function DocsSquares({ docs }: { docs: DocsAggregate }) {
  return (
    <span className="docsq">
      {ENTRIES.map((e) => (
        <span key={e.key} className={docs[e.key] ? '' : 'no'} title={e.title}>
          {e.label}
        </span>
      ))}
    </span>
  )
}
