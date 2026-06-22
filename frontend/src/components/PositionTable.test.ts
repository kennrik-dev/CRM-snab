import { describe, it, expect } from 'vitest'
import {
  isReadOnlyCol,
  colToKey,
  type PositionTableColumn,
} from './PositionTable'

// Mirrors the real column defs in Komplektaciya.tsx (draftColumns) and
// RequestCard.tsx (positionColumns): NONE of the data columns set `readOnly`.
type Row = {
  num?: string | null
  name: string | null
  qty: number | null
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
}

const columns: PositionTableColumn<Row>[] = [
  { key: 'name', header: 'Наименование', width: '1fr' },
  { key: 'qty', header: 'Кол-во', width: '90px', align: 'right', mono: true },
  { key: 'unit', header: 'Ед. изм.', width: '70px', mono: true },
  { key: 'gost_tu', header: 'ГОСТ/ТУ', width: '100px' },
  { key: 'doc_code', header: 'Шифр документации', width: '130px' },
]

describe('isReadOnlyCol — data columns are editable by default (regression for the ?? true bug)', () => {
  // Internal col indexing: 0 = «№», 1..N = data columns.
  it('col 0 (the «№» cell) is always editable when readOnly prop is false', () => {
    expect(isReadOnlyCol(0, columns, false)).toBe(false)
  })

  it('returns false for every data column when none declares readOnly (the bug made these all true)', () => {
    // These were ALL read-only before the fix because `undefined ?? true === true`.
    for (let c = 1; c <= columns.length; c++) {
      expect(isReadOnlyCol(c, columns, false)).toBe(false)
    }
  })

  it('still respects an explicit readOnly: true on a data column', () => {
    const withLocked: PositionTableColumn<Row>[] = [
      ...columns.slice(0, 3),
      { key: 'gost_tu', header: 'ГОСТ/ТУ', width: '100px', readOnly: true },
      { key: 'doc_code', header: 'Шифр', width: '130px' },
    ]
    expect(isReadOnlyCol(4, withLocked, false)).toBe(true) // gost_tu locked
    expect(isReadOnlyCol(5, withLocked, false)).toBe(false) // doc_code still editable
  })

  it('the table-level readOnly prop forces every column read-only', () => {
    expect(isReadOnlyCol(0, columns, true)).toBe(true)
    for (let c = 1; c <= columns.length; c++) {
      expect(isReadOnlyCol(c, columns, true)).toBe(true)
    }
  })
})

describe('colToKey — internal col → data key mapping', () => {
  it('maps col 0 to the synthetic "num" key', () => {
    expect(colToKey(0, columns)).toBe('num')
  })

  it('maps data cols 1..N to columns[col-1].key', () => {
    expect(colToKey(1, columns)).toBe('name')
    expect(colToKey(2, columns)).toBe('qty')
    expect(colToKey(5, columns)).toBe('doc_code')
  })

  it('returns null for an out-of-range data col', () => {
    expect(colToKey(columns.length + 1, columns)).toBeNull()
  })
})

// The combination below is exactly what the paste loop and startEdit rely on:
// if isReadOnlyCol were true for a data col, the cell would be silently
// skipped (paste) or the edit would early-return (startEdit). These two
// helpers together MUST agree that a normal data column is writable AND has
// a resolvable key, otherwise the three reported symptoms reappear.
describe('regression: a data column is writable AND has a resolvable key (paste/edit contract)', () => {
  it('name column (col 1) is editable and resolves to the "name" key', () => {
    expect(isReadOnlyCol(1, columns, false)).toBe(false)
    expect(colToKey(1, columns)).toBe('name')
  })
})
