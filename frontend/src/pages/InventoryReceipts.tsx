import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Decimal from 'decimal.js'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { api, ApiError, errorMessages } from '../api/client'
import type { PaginatedReceiptList, Partner, Receipt } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Empty, Loading, TableWrap, Td, Th } from '../components/common'
import { formatMoney } from '../money'
import { useSession } from '../session'
import { emptyLine, LineEditor, type DocLine } from './InventoryDocs'
import { useWarehouses } from './InventoryReports'

const today = () => new Date().toISOString().slice(0, 10)

export function ReceiptList() {
  const { t } = useTranslation()
  const { can, company } = useSession()
  const list = useQuery({ queryKey: ['receipts', company?.id], queryFn: () => api<PaginatedReceiptList>('/inventory/receipts/') })
  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h3 className="text-lg font-semibold">{t('inventory.receipts')}</h3>
        {can('inventory.receipt') && <Link className="rounded-md bg-slate-900 px-3 py-2 text-sm text-white" to="/inventory/receipts/new">{t('inventory.newReceipt')}</Link>}
      </div>
      <Loading query={list} />
      {list.data && (list.data.results.length === 0 ? <Empty>{t('inventory.noDocs')}</Empty> : (
        <TableWrap>
          <thead><tr><Th>#</Th><Th>{t('journal.date')}</Th><Th end>{t('inventory.total')}</Th><Th>{t('journal.status')}</Th></tr></thead>
          <tbody>
            {list.data.results.map((r) => (
              <tr key={r.id}>
                <Td><Link className="underline" to={`/inventory/receipts/${r.id}`}>{r.number}</Link></Td><Td>{r.date}</Td>
                <Td end>{formatMoney(r.total_cost)}</Td>
                <Td><Badge tone={r.journal_entry_status === 'posted' ? 'green' : 'amber'}>{r.journal_entry_status ? t(`journal.${r.journal_entry_status}`) : '—'}</Badge></Td>
              </tr>
            ))}
          </tbody>
        </TableWrap>
      ))}
    </div>
  )
}

export function ReceiptForm() {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const warehouses = useWarehouses()
  const partners = useQuery({ queryKey: ['partners', company?.id], queryFn: () => api<Partner[]>('/partners/') })
  const existing = useQuery({ queryKey: ['receipt', company?.id, id], enabled: !!id, queryFn: () => api<Receipt>(`/inventory/receipts/${id}/`) })

  const [date, setDate] = useState(today())
  const [warehouse, setWarehouse] = useState('')
  const [supplier, setSupplier] = useState('')
  const [invoice, setInvoice] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<DocLine[]>([emptyLine()])
  const [errors, setErrors] = useState<string[]>([])

  useEffect(() => {
    const r = existing.data
    if (!r) return
    setDate(r.date ?? today()); setWarehouse(String(r.warehouse)); setSupplier(String(r.supplier))
    setInvoice(r.supplier_invoice ?? ''); setNotes(r.notes ?? '')
    setLines(r.lines.map((l) => ({ product: String(l.product), quantity: l.quantity, unit_cost: l.unit_cost })))
  }, [existing.data])

  const locked = existing.data?.locked_reason ?? ''
  const readOnly = !!id && !!locked
  const total = lines.reduce((s, l) => { try { return s.plus(new Decimal(l.quantity || 0).times(l.unit_cost || 0)) } catch { return s } }, new Decimal(0))
  const done = () => { void queryClient.invalidateQueries({ queryKey: ['receipts'] }); void queryClient.invalidateQueries({ queryKey: ['receipt'] }); void queryClient.invalidateQueries({ queryKey: ['stock-levels'] }); navigate('/inventory/receipts') }
  const onError = (e: unknown) => setErrors(e instanceof ApiError ? errorMessages(e.body) : [t('common.loadFailed')])

  const save = useMutation({
    mutationFn: () => {
      const body = JSON.stringify({
        date, warehouse: Number(warehouse), supplier: Number(supplier), supplier_invoice: invoice, notes,
        lines: lines.map((l) => ({ product: Number(l.product), quantity: l.quantity, unit_cost: l.unit_cost })),
      })
      return id ? api(`/inventory/receipts/${id}/`, { method: 'PUT', body }) : api('/inventory/receipts/', { method: 'POST', body })
    },
    onSuccess: done, onError,
  })
  const remove = useMutation({ mutationFn: () => api(`/inventory/receipts/${id}/`, { method: 'DELETE' }), onSuccess: done, onError })
  const suppliers = (partners.data ?? []).filter((p) => p.is_active && (p.kind === 'supplier' || p.kind === 'both'))
  function submit(e: FormEvent) { e.preventDefault(); setErrors([]); save.mutate() }

  if (id) { if (existing.isPending || existing.isError) return <Loading query={existing} /> }
  return (
    <form onSubmit={submit} className="space-y-4">
      <h3 className="text-lg font-semibold">{id ? `${t('inventory.receipt')} ${existing.data?.number}` : t('inventory.newReceipt')}</h3>
      {locked && <p role="status" className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">{locked}</p>}
      <Card>
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label={t('journal.date')}><input type="date" className={inputClass} value={date} disabled={readOnly} onChange={(e) => setDate(e.target.value)} required /></Field>
          <Field label={t('inventory.warehouse')}>
            <select className={inputClass} value={warehouse} disabled={readOnly} onChange={(e) => setWarehouse(e.target.value)} required aria-label={t('inventory.warehouse')}>
              <option value="">—</option>{warehouses.data?.filter((w) => w.is_active).map((w) => <option key={w.id} value={w.id}>{w.code}</option>)}
            </select>
          </Field>
          <Field label={t('inventory.supplier')}>
            <select className={inputClass} value={supplier} disabled={readOnly} onChange={(e) => setSupplier(e.target.value)} required aria-label={t('inventory.supplier')}>
              <option value="">—</option>{suppliers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
          <Field label={t('inventory.supplierInvoice')}><input className={inputClass} value={invoice} disabled={readOnly} onChange={(e) => setInvoice(e.target.value)} maxLength={100} /></Field>
        </div>
      </Card>
      <Card title={t('inventory.lines')}>
        <LineEditor lines={lines} onChange={setLines} withCost readOnly={readOnly} />
        <p className="mt-3 text-end font-semibold">{t('inventory.total')}: <span data-testid="receipt-total" className="tabular-nums">{formatMoney(total)}</span></p>
      </Card>
      <Field label={t('journal.memo')}><input className={inputClass} value={notes} disabled={readOnly} onChange={(e) => setNotes(e.target.value)} maxLength={300} /></Field>
      <ErrorList messages={errors} />
      <div className="flex gap-2">
        {!readOnly && can('inventory.receipt') && <Button type="submit" disabled={save.isPending}>{t('common.save')}</Button>}
        {id && !readOnly && can('inventory.receipt_delete') && (
          <Button type="button" variant="secondary" onClick={() => { if (window.confirm(t('inventory.confirmDelete'))) remove.mutate() }}>{t('common.delete')}</Button>
        )}
        <Link className="px-3 py-2 text-sm underline" to="/inventory/receipts">{t('common.cancel')}</Link>
        {existing.data?.journal_entry && <Link className="px-3 py-2 text-sm underline" to={`/journal/${existing.data.journal_entry}`}>{t('inventory.viewEntry')}</Link>}
      </div>
    </form>
  )
}
