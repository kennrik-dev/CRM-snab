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
 * Внутренняя индексация столбцов (active.col):
 *   0   →  «№» (виртуальная колонка, читает/пишет row.num)
 *   1.. →  columns[active.col - 1] (настоящие данные)
 *
 * API:
 *   rows           — текущие строки
 *   columns        — определения колонок (key, header, width, mono, readOnly)
 *   getRowId       — стабильный id строки
 *   onCellChange   — (rowId, key, value) обновление одной ячейки
 *   onDeleteRow    — (rowId) удаление строки (×)
 *   onAddRows      — (afterRowId | null, count) → string[] — добавление
 *                    N пустых строк. Должен ВЕРНУТЬ id добавленных строк
 *                    (paste использует их, чтобы записать значения
 *                    синхронно, до ре-рендера).
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
  /**
   * Display-only formatter for the non-editing cell render. The editing
   * <input> still uses the raw value. When omitted, the raw value is shown
   * (or '—' / '' per the mono rule below).
   */
  format?: (value: string) => string
}

type Props<T> = {
  rows: T[]
  columns: PositionTableColumn<T>[]
  getRowId: (row: T) => string | number
  onCellChange: (rowId: string | number, key: string, value: string | null) => void
  onDeleteRow: (rowId: string | number) => void
  /**
   * Called when paste needs more rows than the current array has.
   * Must return the ids of the newly-created rows in order.
   */
  onAddRows?: (afterRowId: string | number | null, count: number) => (string | number)[]
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
  cursor: 'cell',
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

const NUM_KEY = 'num' as keyof unknown

// Translate display col → underlying data key (returns 'num' for col 0).
export function colToKey<T>(col: number, columns: PositionTableColumn<T>[]): string | null {
  if (col === 0) return NUM_KEY as string
  const dataCol = columns[col - 1]
  return dataCol ? dataCol.key : null
}

export function isReadOnlyCol<T>(col: number, columns: PositionTableColumn<T>[], readOnly: boolean): boolean {
  if (readOnly) return true
  if (col === 0) return false
  return columns[col - 1]?.readOnly ?? false
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
  // Total number of "logical" columns (data + optional № + delete).
  // The delete column is the last (handled separately in the render).
  const totalLogicalCols = columns.length + (showRowNumber ? 1 : 0)

  const [active, setActive] = useState<CellPos | null>(null)
  const [editing, setEditing] = useState<CellPos | null>(null)
  const [editValue, setEditValue] = useState('')
  const tableRef = useRef<HTMLTableElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

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
    const key = colToKey(editing.col, columns)
    if (key) {
      const current = getCellValue(row, key as keyof T & string)
      if (editValue !== current) {
        onCellChange(getRowId(row), key, editValue === '' ? null : editValue)
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
      if (isReadOnlyCol(pos.col, columns, readOnly)) return
      const row = rows[pos.row]
      if (!row) return
      const key = colToKey(pos.col, columns)
      if (!key) return
      setActive(pos)
      setEditing(pos)
      setEditValue(getCellValue(row, key as keyof T & string))
    },
    [readOnly, rows, columns, getCellValue],
  )

  const moveActive = useCallback(
    (dr: number, dc: number) => {
      if (!active) return
      const newRow = Math.max(0, Math.min(rows.length - 1, active.row + dr))
      const newCol = Math.max(0, Math.min(totalLogicalCols - 1, active.col + dc))
      setActive({ row: newRow, col: newCol })
    },
    [active, rows.length, totalLogicalCols],
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
          if (isReadOnlyCol(active.col, columns, readOnly)) return
          const key = colToKey(active.col, columns)
          if (!key) return
          e.preventDefault()
          onCellChange(getRowId(row), key, null)
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
            // Don't hijack typing into a live input (the «№» cell's own
            // <input>) — let it handle the character natively. Otherwise the
            // first keystroke is swallowed (preventDefault here) while trying
            // to enter edit mode for a column that has no edit mode.
            const tgt = e.target as HTMLElement
            if (tgt.tagName === 'INPUT' || tgt.tagName === 'TEXTAREA') break
            if (!isReadOnlyCol(active.col, columns, readOnly)) {
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
      // Only skip paste when the focus is on a non-numeric INPUT (e.g. a
      // future textarea). The «№» cell's own input has inputMode="numeric"
      // and is our target — let the table handle paste there too.
      const target = e.target as HTMLElement
      if (target.tagName === 'TEXTAREA') return
      if (
        target.tagName === 'INPUT' &&
        (target as HTMLInputElement).inputMode !== 'numeric'
      ) {
        return
      }

      e.preventDefault()
      const lines = text.replace(/\r\n?/g, '\n').split('\n').filter((l) => l.length > 0)
      if (lines.length === 0) return

      const rows2d: string[][] = lines.map((line) => line.split('\t'))
      const startRow = active.row
      const startCol = active.col
      const neededRows = startRow + rows2d.length

      // Grow the table first. The parent must return the new rowIds so we
      // can write to them synchronously (the parent re-renders AFTER this
      // handler returns, so we can't read the new rows from a ref).
      let newRowIds: (string | number)[] = []
      if (neededRows > rows.length && onAddRows) {
        const afterId =
          rows.length > 0 ? getRowId(rows[rows.length - 1]) : null
        newRowIds = onAddRows(afterId, neededRows - rows.length)
      }

      for (let r = 0; r < rows2d.length; r++) {
        const targetRowIdx = startRow + r
        // Resolve the row id: existing row or one of the newly-added rows.
        let rowId: string | number
        if (targetRowIdx < rows.length) {
          rowId = getRowId(rows[targetRowIdx])
        } else {
          const newIdx = targetRowIdx - rows.length
          const newId = newRowIds[newIdx]
          if (newId === undefined) continue
          rowId = newId
        }

        for (let c = 0; c < rows2d[r].length; c++) {
          const targetCol = startCol + c
          if (isReadOnlyCol(targetCol, columns, readOnly)) continue
          const key = colToKey(targetCol, columns)
          if (!key) continue
          const value = rows2d[r][c]
          onCellChange(rowId, key, value === '' ? null : value)
        }
      }
    },
    [readOnly, active, rows, columns, onAddRows, onCellChange, getRowId],
  )

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
            <td colSpan={totalLogicalCols + 1} style={{ textAlign: 'center', color: 'var(--muted)' }}>
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
                  <td
                    style={rowNumberCellStyle}
                    onClick={() => onCellClick(ri, 0)}
                  >
                    {readOnly ? (
                      <span>{getCellValue(row, NUM_KEY as keyof T & string) || '—'}</span>
                    ) : (
                      <input
                        type="text"
                        inputMode="numeric"
                        value={getCellValue(row, NUM_KEY as keyof T & string)}
                        onChange={(e) =>
                          onCellChange(rowId, NUM_KEY as keyof T & string, e.target.value)
                        }
                        onFocus={() => onCellClick(ri, 0)}
                        placeholder="—"
                        style={rowNumberInputStyle}
                      />
                    )}
                  </td>
                )}
                {columns.map((c, ci) => {
                  // Display column index for this data cell: +1 because
                  // column 0 is the «№» column.
                  const displayCol = ci + 1
                  const isActive = active?.row === ri && active?.col === displayCol
                  const isEditing = editing?.row === ri && editing?.col === displayCol
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
                      onClick={() => onCellClick(ri, displayCol)}
                      onDoubleClick={() => onCellDoubleClick(ri, displayCol)}
                    >
                      {c.format ? c.format(value) : (value || (c.mono ? '' : '—'))}
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
