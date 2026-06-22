import type { ReactNode } from 'react'

export type DataTableColumn<T> = {
  key: string
  header: string
  render?: (row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
  // CSS width for the column (e.g. '30%', '120px'). When at least one column
  // specifies a width, the table switches to `table-layout: fixed` and a
  // <colgroup> is rendered so column widths become STATIC — they no longer
  // shift when row content changes (e.g. toggling "Показать отменённые").
  // Leave undefined for content-driven layout (the legacy behaviour).
  width?: string
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
  const hasFixedLayout = columns.some((c) => c.width !== undefined)
  const tableCls = `reg ${hasFixedLayout ? 'fixed ' : ''}${className ?? ''}`.trim()
  const colgroup = hasFixedLayout ? (
    <colgroup>
      {columns.map((c) => (
        <col key={c.key} style={c.width ? { width: c.width } : undefined} />
      ))}
    </colgroup>
  ) : null

  if (rows.length === 0 && empty !== undefined) {
    return (
      <table className={tableCls}>
        {colgroup}
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
      {colgroup}
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
