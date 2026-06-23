import { describe, it, expect } from 'vitest'
import { procStatusChip } from './Zakupka'

// procStatusChip is the pure status→chip mapping used by the list column.
// «Отменена» (service-set by cancel) → cancel chip; NULL/missing → proc chip
// labelled «В закупке»; any known dict value (Торги/Подведение итогов/…) →
// proc chip keeping the value verbatim.
describe('procStatusChip', () => {
  it('maps «Отменена» to the cancel chip', () => {
    expect(procStatusChip('Отменена')).toEqual({
      kind: 'cancel',
      label: 'Отменена',
    })
  })

  it('maps null to a proc chip labelled «В закупке»', () => {
    expect(procStatusChip(null)).toEqual({ kind: 'proc', label: 'В закупке' })
  })

  it('maps undefined to a proc chip labelled «В закупке»', () => {
    expect(procStatusChip(undefined)).toEqual({
      kind: 'proc',
      label: 'В закупке',
    })
  })

  it('maps a known dict status (e.g. «Торги») to a proc chip keeping the label', () => {
    expect(procStatusChip('Торги')).toEqual({ kind: 'proc', label: 'Торги' })
  })

  it('maps «Новая» to a proc chip (service value still displays verbatim)', () => {
    expect(procStatusChip('Новая')).toEqual({ kind: 'proc', label: 'Новая' })
  })

  it('maps an empty string to «В закупке» (treats empty as no status)', () => {
    expect(procStatusChip('')).toEqual({ kind: 'proc', label: 'В закупке' })
  })
})
