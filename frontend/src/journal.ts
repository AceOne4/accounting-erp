import Decimal from 'decimal.js'

export type DraftLine = {
  key: string
  account: string // account id as text, '' when empty
  partner: string
  debit: string
  credit: string
  memo: string
}

export function emptyLine(key: string): DraftLine {
  return { key, account: '', partner: '', debit: '', credit: '', memo: '' }
}

function amount(text: string): Decimal | null {
  const trimmed = text.trim()
  if (trimmed === '') return new Decimal(0)
  try {
    const value = new Decimal(trimmed)
    return value.isFinite() ? value : null
  } catch {
    return null
  }
}

export function totals(lines: DraftLine[]): { debit: Decimal; credit: Decimal } {
  let debit = new Decimal(0)
  let credit = new Decimal(0)
  for (const line of lines) {
    debit = debit.plus(amount(line.debit) ?? 0)
    credit = credit.plus(amount(line.credit) ?? 0)
  }
  return { debit, credit }
}

export function isBalanced(lines: DraftLine[]): boolean {
  const { debit, credit } = totals(lines)
  return debit.gt(0) && debit.eq(credit)
}

/** A line that has any content must be complete; empty lines are ignored on save. */
export function isBlank(line: DraftLine): boolean {
  return !line.account && !line.debit.trim() && !line.credit.trim() && !line.partner && !line.memo.trim()
}

export type LineProblem = 'account' | 'amount' | 'both' | 'decimals' | null

export function lineProblem(line: DraftLine): LineProblem {
  if (isBlank(line)) return null
  const debit = amount(line.debit)
  const credit = amount(line.credit)
  if (!line.account) return 'account'
  if (debit === null || credit === null || debit.isNeg() || credit.isNeg()) return 'amount'
  if (debit.gt(0) && credit.gt(0)) return 'both'
  if (debit.isZero() && credit.isZero()) return 'amount'
  if (debit.decimalPlaces() > 2 || credit.decimalPlaces() > 2) return 'decimals'
  return null
}
