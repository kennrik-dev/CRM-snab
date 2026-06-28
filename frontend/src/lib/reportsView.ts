import type { Cell } from '../api/reports'

export function colorClass(token: string | null | undefined): string {
  if (!token) return ''
  return token.replace(/^--/, '')
}

export type RenderedCell = { className: string; text: string; tag?: string }

export function describeCell(cell: Cell): RenderedCell {
  if (typeof cell === 'string') return { className: '', text: cell }
  const text = cell.text ?? ''
  switch (cell.kind) {
    case 'claim':
      return { className: '', text: cell.title ?? '', tag: cell.code ?? '—' }
    case 'stage':
      return { className: `chip ${colorClass(cell.color)}`.trim(), text }
    case 'days':
      return { className: `daypill ${cell.level || ''}`.trim(), text }
    case 'date-late':
      return { className: 'dt late', text }
    case 'money':
    case 'percent':
      return { className: 'mono', text }
    case 'note':
      return { className: 'cellsub', text }
    default:
      return { className: '', text }
  }
}

export function cellText(cell: Cell): string {
  if (typeof cell === 'string') return cell
  if (cell.kind === 'claim') return `${cell.code ?? '—'} ${cell.title ?? ''}`.trim()
  return cell.text ?? ''
}

export function periodOptionLabel(
  key: '' | 'month' | 'quarter' | 'year' | 'custom',
): string {
  switch (key) {
    case 'month': return 'Текущий месяц'
    case 'quarter': return 'Квартал'
    case 'year': return 'С начала года'
    case 'custom': return 'Произвольный'
    default: return 'Весь период'
  }
}
