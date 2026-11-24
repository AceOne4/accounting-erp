import { describe, expect, it } from 'vitest'

import { emptyLine, isBalanced, lineProblem, totals, type DraftLine } from './journal'

const line = (over: Partial<DraftLine>): DraftLine => ({ ...emptyLine('k'), ...over })

describe('journal helpers', () => {
  it('adds money exactly, without float drift', () => {
    const lines = [line({ debit: '0.1' }), line({ debit: '0.2' }), line({ credit: '0.3' })]
    const t = totals(lines)
    expect(t.debit.toString()).toBe('0.3')
    expect(isBalanced(lines)).toBe(true)
  })

  it('is not balanced when empty or off by a cent', () => {
    expect(isBalanced([])).toBe(false)
    expect(isBalanced([line({ debit: '10.00' }), line({ credit: '9.99' })])).toBe(false)
  })

  it('ignores unparsable amounts in totals instead of crashing', () => {
    expect(totals([line({ debit: 'abc' })]).debit.toString()).toBe('0')
  })

  it('flags problems per line', () => {
    expect(lineProblem(line({}))).toBeNull() // blank lines are skipped
    expect(lineProblem(line({ debit: '5' }))).toBe('account')
    expect(lineProblem(line({ account: '1' }))).toBe('amount')
    expect(lineProblem(line({ account: '1', debit: '5', credit: '5' }))).toBe('both')
    expect(lineProblem(line({ account: '1', debit: '5.001' }))).toBe('decimals')
    expect(lineProblem(line({ account: '1', debit: '-5' }))).toBe('amount')
    expect(lineProblem(line({ account: '1', credit: '5.50' }))).toBeNull()
  })
})
