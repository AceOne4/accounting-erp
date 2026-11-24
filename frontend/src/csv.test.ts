import { describe, expect, it } from 'vitest'

import { tablesToRows, toCsv } from './csv'

describe('toCsv', () => {
  it('quotes commas, quotes and line breaks', () => {
    expect(toCsv([['a,b', 'say "hi"', 'x\ny'], ['1', '2', '3']])).toBe('"a,b","say ""hi""","x\ny"\r\n1,2,3')
  })
  it('reads tables as rows', () => {
    const root = document.createElement('div')
    root.innerHTML = '<table><tr><th>Name</th><th>Total</th></tr><tr><td>Cash</td><td>1,000.00</td></tr></table>'
    expect(tablesToRows(root)).toEqual([['Name', 'Total'], ['Cash', '1,000.00']])
  })
})
