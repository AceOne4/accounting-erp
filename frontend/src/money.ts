import Decimal from 'decimal.js'

// The API sends money as decimal strings. Never convert them to JS numbers.
export function money(value: string | number | Decimal): Decimal {
  return new Decimal(value)
}

/** Debit minus credit, exact. */
export function difference(debit: string, credit: string): Decimal {
  return money(debit).minus(money(credit))
}

/** Two decimals, English digits in every language, thousands separators. */
export function formatMoney(value: string | number | Decimal): string {
  const fixed = money(value).toFixed(2)
  const [whole, cents] = fixed.split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`
}
