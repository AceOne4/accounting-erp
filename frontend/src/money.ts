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

/** Quantities: up to 3 decimals, no trailing zeros. */
export function formatQty(value: string | number | Decimal): string {
  const fixed = money(value).toFixed(3).replace(/\.?0+$/, '')
  const [whole, rest] = fixed.split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return rest ? `${grouped}.${rest}` : grouped
}
