import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../api/client'
import type { ItemCard as ItemCardData, PaginatedProductList, StockLevels as StockLevelsData } from '../api/generated'
import { Badge, Field, inputClass } from '../components/ui'
import { Card, Empty, Loading, TableWrap, Td, Th } from '../components/common'
import { formatMoney, formatQty } from '../money'
import { localName } from '../names'
import { useWarehouses } from '../inventoryData'
import { useSession } from '../sessionContext'

export function StockLevels() {
  const { t, i18n } = useTranslation()
  const { company } = useSession()
  const warehouses = useWarehouses()
  const [warehouse, setWarehouse] = useState('')
  const [q, setQ] = useState('')
  const params = new URLSearchParams()
  if (warehouse) params.set('warehouse', warehouse)
  if (q.trim()) params.set('q', q.trim())
  const levels = useQuery({ queryKey: ['stock-levels', company?.id, params.toString()], queryFn: () => api<StockLevelsData>(`/inventory/reports/stock-levels/?${params}`) })
  const d = levels.data
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t('inventory.warehouse')}>
          <select className={inputClass} value={warehouse} onChange={(e) => setWarehouse(e.target.value)}>
            <option value="">{t('inventory.allWarehouses')}</option>
            {warehouses.data?.map((w) => <option key={w.id} value={w.id}>{w.code} - {localName(w, i18n.language)}</option>)}
          </select>
        </Field>
        <Field label={t('common.search')}><input className={inputClass} value={q} onChange={(e) => setQ(e.target.value)} /></Field>
      </div>
      <Loading query={levels} />
      {d && (
        <>
          {d.rows.length === 0 ? <Empty>{t('inventory.noStock')}</Empty> : (
            <TableWrap>
              <thead><tr><Th>{t('inventory.product')}</Th><Th>{t('inventory.warehouse')}</Th><Th end>{t('inventory.qty')}</Th><Th end>{t('inventory.avgCost')}</Th><Th end>{t('inventory.value')}</Th></tr></thead>
              <tbody>
                {d.rows.map((r) => (
                  <tr key={`${r.product}-${r.warehouse}`}>
                    <Td>{r.product_code} - {r.product_name}</Td><Td>{r.warehouse_code}</Td>
                    <Td end>{formatQty(r.qty)} {r.unit}</Td><Td end>{formatMoney(r.avg_cost)}</Td><Td end>{formatMoney(r.value)}</Td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr className="bg-slate-50 font-semibold"><Td>{t('report.total')}</Td><Td /><Td end /><Td end /><Td end><span data-testid="levels-total">{formatMoney(d.total_value)}</span></Td></tr></tfoot>
            </TableWrap>
          )}
          {d.ledger && (
            <Card title={t('inventory.ledgerCheck')}>
              <dl className="grid gap-2 text-sm sm:grid-cols-4">
                <div><dt className="text-slate-500">{t('inventory.stockValue')}</dt><dd className="tabular-nums">{formatMoney(d.stock_total)}</dd></div>
                <div><dt className="text-slate-500">{t('inventory.ledgerAll')}</dt><dd className="tabular-nums">{formatMoney(d.ledger.all)}</dd></div>
                <div><dt className="text-slate-500">{t('inventory.ledgerPosted')}</dt><dd className="tabular-nums">{formatMoney(d.ledger.posted)}</dd></div>
                <div><dt className="text-slate-500">{t('inventory.difference')}</dt>
                  <dd><Badge tone={Number(d.ledger.difference) === 0 ? 'green' : 'amber'}>{formatMoney(d.ledger.difference)}</Badge></dd></div>
              </dl>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export function ItemCard() {
  const { t, i18n } = useTranslation()
  const { company } = useSession()
  const warehouses = useWarehouses()
  const products = useQuery({ queryKey: ['products-all', company?.id], queryFn: () => api<PaginatedProductList>('/inventory/products/?active=1') })
  const [product, setProduct] = useState('')
  const [warehouse, setWarehouse] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const params = new URLSearchParams({ product })
  if (warehouse) params.set('warehouse', warehouse)
  if (from) params.set('date_from', from)
  if (to) params.set('date_to', to)
  const card = useQuery({ queryKey: ['item-card', company?.id, params.toString()], enabled: !!product, queryFn: () => api<ItemCardData>(`/inventory/reports/item-card/?${params}`) })
  const d = card.data
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label={t('inventory.product')}>
          <select className={inputClass} value={product} onChange={(e) => setProduct(e.target.value)} aria-label={t('inventory.product')}>
            <option value="">—</option>
            {products.data?.results.map((p) => <option key={p.id} value={p.id}>{p.code} - {localName(p, i18n.language)}</option>)}
          </select>
        </Field>
        <Field label={t('inventory.warehouse')}>
          <select className={inputClass} value={warehouse} onChange={(e) => setWarehouse(e.target.value)}>
            <option value="">{t('inventory.allWarehouses')}</option>
            {warehouses.data?.map((w) => <option key={w.id} value={w.id}>{w.code}</option>)}
          </select>
        </Field>
        <Field label={t('report.from')}><input type="date" className={inputClass} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label={t('report.to')}><input type="date" className={inputClass} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
      </div>
      {!product && <Empty>{t('inventory.pickProduct')}</Empty>}
      {product && <Loading query={card} />}
      {d && (
        <TableWrap>
          <thead><tr><Th>{t('journal.date')}</Th><Th>{t('inventory.document')}</Th><Th end>{t('inventory.in')}</Th><Th end>{t('inventory.out')}</Th><Th end>{t('inventory.value')}</Th><Th end>{t('inventory.balanceQty')}</Th><Th end>{t('inventory.balanceValue')}</Th></tr></thead>
          <tbody>
            <tr className="bg-slate-50"><Td>{t('report.opening')}</Td><Td /><Td end /><Td end /><Td end /><Td end>{formatQty(d.opening_qty)}</Td><Td end>{formatMoney(d.opening_value)}</Td></tr>
            {d.rows.map((r, i) => (
              <tr key={i}>
                <Td>{r.date}</Td><Td>{t(`inventory.docTypes.${r.doc_type}`, r.doc_type)} {r.doc_number}</Td>
                <Td end>{r.qty_in ? formatQty(r.qty_in) : ''}</Td><Td end>{r.qty_out ? formatQty(r.qty_out) : ''}</Td>
                <Td end>{formatMoney(r.value)}</Td><Td end>{formatQty(r.balance_qty)}</Td><Td end>{formatMoney(r.balance_value)}</Td>
              </tr>
            ))}
          </tbody>
        </TableWrap>
      )}
    </div>
  )
}
