/**
 * PositionTable — компактная таблица позиций в стиле канона `.postbl`
 * (`Concept design/zakupki-crm.css`). В отличие от ExcelTable, это обычная
 * HTML `<table>`, поэтому:
 *   - нет горизонтального скролла — ширины колонок заданы явно через colgroup;
 *   - визуальный стиль 1-в-1 как в референсе (тонкий border-bottom, monospace
 *     для qty/unit, uppercase серые заголовки);
 *   - поддержка вставки из Excel/Sheets через TSV (clipboard text/plain);
 *   - клик → выбор ячейки; F2 или начало ввода → редактирование;
 *     Enter / Tab → коммит + переход; Esc → отмена.
 *
 * API:
 *   rows           — текущие строки
 *   columns        — определения колонок (key, header, width, mono, readOnly)
 *   getRowId       — стабильный id строки
 *   onCellChange   — (rowId, key, value) обновление одной ячейки
 *   onDeleteRow    — (rowId) удаление строки (×)
 *   onAddRows      — (afterRowId | null, count) добавление N пустых строк
 *                    (вызывается при paste, если строк не хватает)
 *   readOnly       — запретить всё редактирование
 *   showRowNumber  — добавить колонку «№» слева (ручной ввод)
 *   emptyMessage   — текст, когда строк 0
 */
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react'

export type PositionTableColumn<T> = {
  key: keyof T & string
  header: string
  /** CSS width of the column (e.g. "40px", "12%"). Applied via <colgroup>. */
  width?: string
  /** Right-align the cell (numeric columns). */
  align?: 'right' | 'left' | 'center'
  /** Use the IBM Plex Mono font (numeric cells). */
  mono?: boolean
  /** Disable editing for this column. */
  readOnly?: boolean
}

/**
 * The `num` field on rows is optional and read/written via the leading «№»
 * column. To keep the component generic, callers can pass any row shape —
 * the «№» cell uses a runtime check (`num` in row) rather than a TS
 * constraint. The field is treated as UI metadata; the parent's
 * `onCellChange` decides whether to forward it to the server.
 */
type Props<T> = {
  rows: T[]
  columns: PositionTableColumn<T>[]
  getRowId: (row: T) => string | number
  onCellChange: (rowId: string | number, key: string, value: string | null) => void
  onDeleteRow: (rowId: string | number) => void
  /** Called when paste needs more rows than the current array has. */
  onAddRows?: (afterRowId: string | number | null, count: number) => void
  readOnly?: boolean
  showRowNumber?: boolean
  emptyMessage?: string
}

type CellPos = { row: number; col: number }

const deleteBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 0,
  color: 'var(--late)',
  cursor: 'pointer',
  fontSize: 16,
  padding: '0 4px',
  lineHeight: 1,
  borderRadius: 3,
}

// Leading «№» column — manual text input, monospace, no auto-numbering.
const rowNumberCellStyle: CSSProperties = {
  padding: 0,
  textAlign: 'center',
  fontFamily: 'var(--mono)',
  fontSize: 12,
  color: 'var(--faint)',
}

const rowNumberInputStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  border: 0,
  outline: 'none',
  background: 'transparent',
  font: 'inherit',
  fontFamily: 'var(--mono)',
  textAlign: 'center',
  color: 'var(--ink)',
  padding: '9px 4px',
}

export function PositionTable<T>({
  rows,
  columns,
  getRowId,
  onCellChange,
  onDeleteRow,
  onAddRows,
  readOnly = false,
  showRowNumber = true,
  emptyMessage = 'Нет позиций',
}: Props<T>) {
  // Offset of the data columns inside the table — accounts for the optional
  // leading "№" column.
  const dataColOffset = showRowNumber ? 1 : 0
  const totalCols = columns.length + dataColOffset + 1 // + delete column

  const [active, setActive] = useState<CellPos | null>(null)
  const [editing, setEditing] = useState<CellPos | null>(null)
  const [editValue, setEditValue] = useState('')
  const tableRef = useRef<HTMLTableElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  // Focus the editor when we enter edit mode.
  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const getCellValue = useCallback(
    (row: T, key: keyof T & string): string => {
      const v = (row as Record<string, unknown>)[key]
      if (v === null || v === undefined) return ''
      return String(v)
    },
    [],
  )

  const commitEdit = useCallback(() => {
    if (!editing) return
    const row = rows[editing.row]
    if (!row) {
      setEditing(null)
      return
    }
    const col = columns[editing.col]
    if (col) {
      const current = getCellValue(row, col.key)
      if (editValue !== current) {
        onCellChange(getRowId(row), col.key, editValue === '' ? null : editValue)
      }
    }
    setEditing(null)
  }, [editing, editValue, rows, columns, onCellChange, getRowId, getCellValue])

  const cancelEdit = useCallback(() => {
    setEditing(null)
    setEditValue('')
  }, [])

  const startEdit = useCallback(
    (pos: CellPos) => {
      if (readOnly) return
      const row = rows[pos.row]
      if (!row) return
      const col = columns[pos.col]
      if (!col || col.readOnly) return
      setActive(pos)
      setEditing(pos)
      setEditValue(getCellValue(row, col.key))
    },
    [readOnly, rows, columns, getCellValue],
  )

  const moveActive = useCallback(
    (dr: number, dc: number) => {
      if (!active) return
      const newRow = Math.max(0, Math.min(rows.length - 1, active.row + dr))
      const newCol = Math.max(
        0,
        Math.min(columns.length - 1, active.col + dc),
      )
      setActive({ row: newRow, col: newCol })
    },
    [active, rows.length, columns.length],
  )

  const handleKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLTableElement>) => {
      if (editing) {
        if (e.key === 'Enter') {
          e.preventDefault()
          commitEdit()
          moveActive(1, 0)
        } else if (e.key === 'Tab') {
          e.preventDefault()
          commitEdit()
          moveActive(0, e.shiftKey ? -1 : 1)
        } else if (e.key === 'Escape') {
          e.preventDefault()
          cancelEdit()
        }
        return
      }

      if (!active) return

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault()
          moveActive(-1, 0)
          break
        case 'ArrowDown':
          e.preventDefault()
          moveActive(1, 0)
          break
        case 'ArrowLeft':
          e.preventDefault()
          moveActive(0, -1)
          break
        case 'ArrowRight':
        case 'Tab':
          e.preventDefault()
          moveActive(0, e.shiftKey ? -1 : 1)
          break
        case 'Enter':
        case 'F2':
          e.preventDefault()
          startEdit(active)
          break
        case 'Delete':
        case 'Backspace': {
          if (readOnly) return
          const row = rows[active.row]
          if (!row) return
          const col = columns[active.col]
          if (!col || col.readOnly) return
          e.preventDefault()
          onCellChange(getRowId(row), col.key, null)
          break
        }
        default:
          // Printable single char: start editing with that value.
          if (
            !readOnly &&
            e.key.length === 1 &&
            !e.ctrlKey &&
            !e.metaKey &&
            !e.altKey
          ) {
            const col = columns[active.col]
            if (col && !col.readOnly) {
              e.preventDefault()
              setEditing(active)
              setEditValue(e.key)
            }
          }
          break
      }
    },
    [
      editing,
      commitEdit,
      cancelEdit,
      moveActive,
      active,
      startEdit,
      readOnly,
      rows,
      columns,
      onCellChange,
      getRowId,
    ],
  )

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTableElement>) => {
      if (readOnly || !active) return
      const text = e.clipboardData.getData('text/plain')
      if (!text) return
      // Skip the paste if the focus is actually on an input/textarea — let
      // the browser handle native paste in that case.
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

      e.preventDefault()
      const lines = text.replace(/\r\n?/g, '\n').split('\n').filter((l) => l.length > 0)
      if (lines.length === 0) return

      const rows2d: string[][] = lines.map((line) => line.split('\t'))
      const startRow = active.row
      const startCol = active.col
      const neededRows = startRow + rows2d.length

      // Grow the table if paste needs more rows.
      if (neededRows > rows.length && onAddRows) {
        const afterId =
          rows.length > 0 ? getRowId(rows[rows.length - 1]) : null
        onAddRows(afterId, neededRows - rows.length)
      }

      // For each (r, c) in the pasted range, set the value.
      // We schedule this on the next microtask so the state from onAddRows
      // (if any) has been applied before we read rows for writing.
      queueMicrotask(() => {
        for (let r = 0; r < rows2d.length; r++) {
          const targetRowIdx = startRow + r
          const targetRow = rowsRef.current[targetRowIdx]
          if (!targetRow) continue
          const rowId = getRowId(targetRow)
          for (let c = 0; c < rows2d[r].length; c++) {
            const targetColIdx = startCol + c
            const col = columns[targetColIdx]
            if (!col || col.readOnly) continue
            onCellChange(rowId, col.key, rows2d[r][c] === '' ? null : rows2d[r][c])
          }
        }
      })
    },
    [readOnly, active, rows, columns, onAddRows, onCellChange, getRowId],
  )

  // Keep a live ref to rows so the microtask in handlePaste reads the
  // post-grow array (parent re-renders before microtask runs).
  const rowsRef = useRef(rows)
  useEffect(() => {
    rowsRef.current = rows
  }, [rows])

  const onCellClick = useCallback(
    (rowIdx: number, colIdx: number) => {
      setActive({ row: rowIdx, col: colIdx })
      setEditing(null)
    },
    [],
  )

  const onCellDoubleClick = useCallback(
    (rowIdx: number, colIdx: number) => {
      startEdit({ row: rowIdx, col: colIdx })
    },
    [startEdit],
  )

  if (rows.length === 0) {
    return (
      <table className="postbl">
        <tbody>
          <tr>
            <td colSpan={totalCols} style={{ textAlign: 'center', color: 'var(--muted)' }}>
              {emptyMessage}
            </td>
          </tr>
        </tbody>
      </table>
    )
  }

  // Build the colgroup with explicit widths so the table NEVER overflows.
  const cols: ReactNode[] = []
  if (showRowNumber) cols.push(<col key="__num" style={{ width: '40px' }} />)
  for (const c of columns) {
    cols.push(<col key={c.key} style={{ width: c.width ?? 'auto' }} />)
  }
  cols.push(<col key="__del" style={{ width: '40px' }} />)

  return (
    <div
      style={{
        border: '1px solid var(--line-soft)',
        borderRadius: 6,
        background: 'var(--surface)',
      }}
    >
      <table
        ref={tableRef}
        className="postbl"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        style={{ tableLayout: 'fixed', width: '100%' }}
      >
        <colgroup>{cols}</colgroup>
        <thead>
          <tr>
            {showRowNumber && <th style={{ width: 40 }}>№</th>}
            {columns.map((c) => (
              <th
                key={c.key}
                style={{
                  width: c.width,
                  textAlign: c.align ?? 'left',
                }}
              >
                {c.header}
              </th>
            ))}
            <th style={{ width: 40 }} aria-label="Действие" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => {
            const rowId = getRowId(row)
            return (
              <tr key={rowId}>
                {showRowNumber && (
                  <td style={rowNumberCellStyle}>
                    {readOnly ? (
                      <span>{getCellValue(row, 'num' as keyof T & string) || '—'}</span>
                    ) : (
                      <input
                        type="text"
                        inputMode="numeric"
                        value={getCellValue(row, 'num' as keyof T & string)}
                        onChange={(e) =>
                          onCellChange(rowId, 'num' as keyof T & string, e.target.value)
                        }
                        onClick={(e) => e.stopPropagation()}
                        placeholder="—"
                        style={rowNumberInputStyle}
                      />
                    )}
                  </td>
                )}
                {columns.map((c, ci) => {
                  const isActive = active?.row === ri && active?.col === ci
                  const isEditing = editing?.row === ri && editing?.col === ci
                  const cellStyle: CSSProperties = {
                    textAlign: c.align ?? 'left',
                    fontFamily: c.mono ? 'var(--mono)' : undefined,
                    background: isActive ? 'var(--hov)' : undefined,
                    cursor: c.readOnly || readOnly ? 'default' : 'cell',
                    padding: 0,
                    overflow: 'hidden',
                  }
                  if (isEditing) {
                    return (
                      <td key={c.key} style={cellStyle}>
                        <input
                          ref={inputRef}
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={commitEdit}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              commitEdit()
                              moveActive(1, 0)
                            } else if (e.key === 'Tab') {
                              e.preventDefault()
                              commitEdit()
                              moveActive(0, e.shiftKey ? -1 : 1)
                            } else if (e.key === 'Escape') {
                              e.preventDefault()
                              cancelEdit()
                            }
                            e.stopPropagation()
                          }}
                          style={{
                            width: '100%',
                            height: '100%',
                            border: '2px solid var(--ink)',
                            outline: 'none',
                            padding: '9px 14px',
                            font: 'inherit',
                            fontFamily: c.mono ? 'var(--mono)' : 'inherit',
                            textAlign: c.align ?? 'left',
                            background: 'var(--surface)',
                          }}
                        />
                      </td>
                    )
                  }
                  const value = getCellValue(row, c.key)
                  return (
                    <td
                      key={c.key}
                      style={cellStyle}
                      onClick={() => onCellClick(ri, ci)}
                      onDoubleClick={() => onCellDoubleClick(ri, ci)}
                    >
                      {value || (c.mono ? '' : '—')}
                    </td>
                  )
                })}
                <td style={{ textAlign: 'center', padding: '6px 4px' }}>
                  {!readOnly && (
                    <button
                      type="button"
                      onClick={() => onDeleteRow(rowId)}
                      title="Удалить позицию"
                      aria-label="Удалить позицию"
                      style={deleteBtnStyle}
                    >
                      ×
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
