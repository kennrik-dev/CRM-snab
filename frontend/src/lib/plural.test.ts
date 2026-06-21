import { describe, it, expect } from 'vitest'
import { pluralRequests } from './plural'

describe('pluralRequests', () => {
  it('returns "заявка" for 1', () => {
    expect(pluralRequests(1)).toBe('заявка')
  })

  it('returns "заявки" for 2', () => {
    expect(pluralRequests(2)).toBe('заявки')
  })

  it('returns "заявки" for 3', () => {
    expect(pluralRequests(3)).toBe('заявки')
  })

  it('returns "заявки" for 4', () => {
    expect(pluralRequests(4)).toBe('заявки')
  })

  it('returns "заявок" for 5', () => {
    expect(pluralRequests(5)).toBe('заявок')
  })

  it('returns "заявок" for 11', () => {
    expect(pluralRequests(11)).toBe('заявок')
  })

  it('returns "заявок" for 12', () => {
    expect(pluralRequests(12)).toBe('заявок')
  })

  it('returns "заявок" for 14', () => {
    expect(pluralRequests(14)).toBe('заявок')
  })

  it('returns "заявок" for 21 (teens exception applies)', () => {
    // 21 is NOT a teen; ru plural rule: ones digit 1 (mod 10) but not teens
    expect(pluralRequests(21)).toBe('заявка')
  })

  it('returns "заявок" for 22', () => {
    expect(pluralRequests(22)).toBe('заявки')
  })

  it('returns "заявки" for 101', () => {
    expect(pluralRequests(101)).toBe('заявка')
  })

  it('returns "заявок" for 111 (teens exception)', () => {
    expect(pluralRequests(111)).toBe('заявок')
  })

  it('returns "заявок" for 0', () => {
    expect(pluralRequests(0)).toBe('заявок')
  })
})
