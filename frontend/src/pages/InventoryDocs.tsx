import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { api } from '../api/client'
import type { PaginatedProductList } from '../api/generated'
import { inputClass } from '../components/ui'
import { localName } from '../names'
import { useSession } from '../session'

export type DocLine = { product: string; quantity: string; unit_cost?: string; counted_qty?: string }

export function useProducts() {
  const { company } = useSession()
  return useQuery({
    queryKey: ['products-all', company?.id],
    queryFn: () => api<PaginatedProductList>('/inventory/products/?active=1&page_size=1000'),
  })
}

/** Rows of product + number fields shared by receipts, transfers and counts. */
export function LineEditor({
  lines, onChange, qtyKey = 'quantity', withCost = false, readOnly = false,
}: {
  lines: DocLine[]
  onChange: (lines: DocLine[]) => void
  qtyKey?: 'quantity' | 'counted_qty'
  withCost?: boolean
  readOnly?: boolean
}) {
  const { t, i18n } = useTranslation()
  const products = useProducts()
  const set = (i: number, patch: Partial<DocLine>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  return (
    <div className="space-y-2">
      {lines.map((l, i) => (
        <div key={i} className={`grid gap-2 ${withCost ? 'sm:grid-cols-[1fr_8rem_8rem_auto]' : 'sm:grid-cols-[1fr_8rem_auto]'}`}>
          <select className={inputClass} value={l.product} disabled={readOnly} aria-label={t('inventory.product')} onChange={(e) => set(i, { product: e.target.value })}>
            <option value="">—</option>
            {products.data?.results.map((p) => <option key={p.id} value={p.id}>{p.code} - {localName(p, i18n.language)}</option>)}
          </select>
          <input inputMode="decimal" dir="ltr" className={`${inputClass} text-end`} value={l[qtyKey] ?? ''} disabled={readOnly}
            aria-label={t('inventory.qty')} placeholder={t('inventory.qty')} onChange={(e) => set(i, { [qtyKey]: e.target.value })} />
          {withCost && (
            <input inputMode="decimal" dir="ltr" className={`${inputClass} text-end`} value={l.unit_cost ?? ''} disabled={readOnly}
              aria-label={t('inventory.unitCost')} placeholder={t('inventory.unitCost')} onChange={(e) => set(i, { unit_cost: e.target.value })} />
          )}
          {!readOnly && (
            <button type="button" className="px-2 text-red-700" aria-label={t('common.delete')} disabled={lines.length === 1}
              onClick={() => onChange(lines.filter((_, j) => j !== i))}>×</button>
          )}
        </div>
      ))}
      {!readOnly && (
        <button type="button" className="text-sm underline" onClick={() => onChange([...lines, { product: '', quantity: '', unit_cost: '', counted_qty: '' }])}>
          + {t('inventory.addLine')}
        </button>
      )}
    </div>
  )
}

export const emptyLine = (): DocLine => ({ product: '', quantity: '', unit_cost: '', counted_qty: '' })
