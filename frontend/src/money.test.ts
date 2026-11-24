import { describe, expect, it } from 'vitest'

import { difference, formatMoney } from './money'

describe('money', () => {
  it('adds without floating point error', () => {
    expect(difference('0.30', '0.20').toFixed(2)).toBe('0.10')
    expect(difference('0.1', '0').plus('0.2').toString()).toBe('0.3')
  })

  it('formats with separators and English digits', () => {
    expect(formatMoney('1234567.5')).toBe('1,234,567.50')
    expect(formatMoney('0')).toBe('0.00')
  })

  it('reports an unbalanced entry', () => {
    expect(difference('1000.00', '900.00').isZero()).toBe(false)
    expect(difference('1000.00', '1000.00').isZero()).toBe(true)
  })
})
