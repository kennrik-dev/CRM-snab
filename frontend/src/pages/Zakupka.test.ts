import { describe, it, expect } from 'vitest'
import { procStatusChip } from './Zakupka'

// procStatusChip is the pure status→chip mapping used by the list column and the
// card. Each status_zakup value gets its OWN color (like Комплектация's colored
// chips), so the 6 справочник values + «Новая» + «Отменена» are distinct.
describe('procStatusChip', () => {
  it('maps «Отменена» to the cancel chip', () => {
    expect(procStatusChip('Отменена')).toEqual({
      kind: 'cancel',
      label: 'Отменена',
    })
  })

  it('maps null/undefined/"" to a wait chip labelled «В закупке»', () => {
    expect(procStatusChip(null)).toEqual({ kind: 'wait', label: 'В закупке' })
    expect(procStatusChip(undefined)).toEqual({ kind: 'wait', label: 'В закупке' })
    expect(procStatusChip('')).toEqual({ kind: 'wait', label: 'В закупке' })
  })

  it('maps «Новая» to a wait chip (service value, neutral start)', () => {
    expect(procStatusChip('Новая')).toEqual({ kind: 'wait', label: 'Новая' })
  })

  it('gives each справочник status its own color kind', () => {
    expect(procStatusChip('Приём заявок')).toEqual({ kind: 'proc', label: 'Приём заявок' })
    expect(procStatusChip('Торги')).toEqual({ kind: 'supp', label: 'Торги' })
    expect(procStatusChip('Тех. экспертиза')).toEqual({ kind: 'pay', label: 'Тех. экспертиза' })
    expect(procStatusChip('Дозапросы')).toEqual({ kind: 'late', label: 'Дозапросы' })
    expect(procStatusChip('Согласование')).toEqual({ kind: 'teal', label: 'Согласование' })
    expect(procStatusChip('На сделку')).toEqual({ kind: 'ok', label: 'На сделку' })
  })

  it('falls back to the proc chip for an unknown status', () => {
    expect(procStatusChip('Что-то новое')).toEqual({ kind: 'proc', label: 'Что-то новое' })
  })
})
