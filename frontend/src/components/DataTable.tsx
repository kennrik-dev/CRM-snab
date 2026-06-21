import type { ReactNode } from 'react'

export type DataTableColumn<T> = {
  key: string
  header: string
  render?: (row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  onRowClick,
  empty,
  className,
}: {
  columns: DataTableColumn<T>[]
  rows: T[]
  getRowId: (row: T) => string | number
  onRowClick?: (row: T) => void
  empty?: ReactNode
  className?: string
}) {
  const tableCls = `reg ${className ?? ''}`.trim()

  if (rows.length === 0 && empty !== undefined) {
    return (
      <table className={tableCls}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.align === 'right' ? 'r' : c.align === 'center' ? 'c' : undefined}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={columns.length} className="empty-state">
              {empty}
            </td>
          </tr>
        </tbody>
      </table>
    )
  }

  return (
    <table className={tableCls}>
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key} className={c.align === 'right' ? 'r' : c.align === 'center' ? 'c' : undefined}>
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={getRowId(row)} onClick={onRowClick ? () => onRowClick(row) : undefined}>
            {columns.map((c) => (
              <td key={c.key} className={c.align === 'right' ? 'r' : c.align === 'center' ? 'c' : undefined}>
                {c.render ? c.render(row) : (row as Record<string, ReactNode>)[c.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
