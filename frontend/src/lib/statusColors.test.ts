import { describe, it, expect } from 'vitest'
import { procStatusChip } from './statusColors'

// procStatusChip: each status_zakup value gets its OWN color; RED (late) is
// reserved for «Отменена» only.
describe('procStatusChip', () => {
  it('maps «Отменена» to the red (late) chip — the ONLY red status', () => {
    expect(procStatusChip('Отменена')).toEqual({ kind: 'late', label: 'Отменена' })
  })

  it('maps null/undefined/"" to a wait chip labelled «В закупке»', () => {
    expect(procStatusChip(null)).toEqual({ kind: 'wait', label: 'В закупке' })
    expect(procStatusChip(undefined)).toEqual({ kind: 'wait', label: 'В закупке' })
    expect(procStatusChip('')).toEqual({ kind: 'wait', label: 'В закупке' })
  })

  it('maps «Новая» to a wait chip (service value, neutral start)', () => {
    expect(procStatusChip('Новая')).toEqual({ kind: 'wait', label: 'Новая' })
  })

  it('gives each справочник status its own non-red color kind', () => {
    expect(procStatusChip('Приём заявок')).toEqual({ kind: 'proc', label: 'Приём заявок' })
    expect(procStatusChip('Торги')).toEqual({ kind: 'supp', label: 'Торги' })
    expect(procStatusChip('Тех. экспертиза')).toEqual({ kind: 'pay', label: 'Тех. экспертиза' })
    expect(procStatusChip('Дозапросы')).toEqual({ kind: 'teal', label: 'Дозапросы' })
    expect(procStatusChip('Согласование')).toEqual({ kind: 'rose', label: 'Согласование' })
    expect(procStatusChip('На сделку')).toEqual({ kind: 'ok', label: 'На сделку' })
  })

  it('never returns red (late) for any non-Отменена status', () => {
    const nonRed = ['Новая', 'Приём заявок', 'Торги', 'Тех. экспертиза', 'Дозапросы', 'Согласование', 'На сделку', '', 'что-то']
    for (const s of nonRed) {
      expect(procStatusChip(s).kind).not.toBe('late')
    }
  })

  it('falls back to the proc chip for an unknown status', () => {
    expect(procStatusChip('Что-то новое')).toEqual({ kind: 'proc', label: 'Что-то новое' })
  })
})
