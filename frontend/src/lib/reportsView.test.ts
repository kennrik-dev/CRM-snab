import { describe, it, expect } from 'vitest'
import {
  colorClass, describeCell, cellText, periodOptionLabel,
} from './reportsView'

describe('reportsView', () => {
  it('colorClass strips the -- prefix', () => {
    expect(colorClass('--proc')).toBe('proc')
    expect(colorClass('--supp')).toBe('supp')
    expect(colorClass(undefined)).toBe('')
    expect(colorClass(null)).toBe('')
  })

  it('describeCell: plain string passthrough', () => {
    expect(describeCell('ООО Ромашка')).toEqual({ className: '', text: 'ООО Ромашка' })
  })

  it('describeCell: claim → tag (code) + text (title)', () => {
    expect(describeCell({ kind: 'claim', code: 'Т-67', title: 'Трубы' }))
      .toEqual({ className: '', text: 'Трубы', tag: 'Т-67' })
  })

  it('describeCell: days → daypill + level class', () => {
    expect(describeCell({ kind: 'days', text: '12 дн.', level: 'warn' }))
      .toEqual({ className: 'daypill warn', text: '12 дн.' })
    expect(describeCell({ kind: 'days', text: '2 дн.', level: '' }))
      .toEqual({ className: 'daypill', text: '2 дн.' })
  })

  it('describeCell: stage → chip + colorClass', () => {
    expect(describeCell({ kind: 'stage', text: 'В закупке', color: '--proc' }))
      .toEqual({ className: 'chip proc', text: 'В закупке' })
  })

  it('describeCell: date-late / money / percent / note', () => {
    expect(describeCell({ kind: 'date-late', text: '01.04.26' }))
      .toEqual({ className: 'dt late', text: '01.04.26' })
    expect(describeCell({ kind: 'money', text: '1 500 ₽' }))
      .toEqual({ className: 'mono', text: '1 500 ₽' })
    expect(describeCell({ kind: 'percent', text: '40%' }))
      .toEqual({ className: 'mono', text: '40%' })
    expect(describeCell({ kind: 'note', text: 'нет' }))
      .toEqual({ className: 'cellsub', text: 'нет' })
  })

  it('cellText: claim concatenates code + title', () => {
    expect(cellText({ kind: 'claim', code: 'Т-67', title: 'Трубы' })).toBe('Т-67 Трубы')
    expect(cellText('plain')).toBe('plain')
  })

  it('periodOptionLabel', () => {
    expect(periodOptionLabel('month')).toBe('Текущий месяц')
    expect(periodOptionLabel('quarter')).toBe('Квартал')
    expect(periodOptionLabel('year')).toBe('С начала года')
    expect(periodOptionLabel('custom')).toBe('Произвольный')
    expect(periodOptionLabel('')).toBe('Весь период')
  })
})
