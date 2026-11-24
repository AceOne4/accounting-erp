import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { api, ApiError, errorMessages } from '../api/client'
import type { Count, PaginatedCountList } from '../api/generated'
import { Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Empty, Loading, TableWrap, Td, Th } from '../components/common'
import { formatQty } from '../money'
import { useSession } from '../session'
import { emptyLine, LineEditor, type DocLine } from './InventoryDocs'
import { useWarehouses } from './InventoryReports'

export function CountList() {
  const { t } = useTranslation()
  const { can, company } = useSession()
  const list = useQuery({ queryKey: ['counts', company?.id], queryFn: () => api<PaginatedCountList>('/inventory/counts/') })
  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h3 className="text-lg font-semibold">{t('inventory.counts')}</h3>
        {can('inventory.count') && <Link className="rounded-md bg-slate-900 px-3 py-2 text-sm text-white" to="/inventory/counts/new">{t('inventory.newCount')}</Link>}
      </div>
      <Loading query={list} />
      {list.data && (list.data.results.length === 0 ? <Empty>{t('inventory.noDocs')}</Empty> : (
        <TableWrap>
          <thead><tr><Th>#</Th><Th>{t('journal.date')}</Th><Th>{t('inventory.by')}</Th></tr></thead>
          <tbody>
            {list.data.results.map((c) => (
              <tr key={c.id}><Td><Link className="underline" to={`/inventory/counts/${c.id}`}>{c.number}</Link></Td><Td>{c.counted_at.slice(0, 10)}</Td><Td>{c.counted_by}</Td></tr>
            ))}
          </tbody>
        </TableWrap>
      ))}
    </div>
  )
}

export function CountForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const warehouses = useWarehouses()
  const [warehouse, setWarehouse] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<DocLine[]>([emptyLine()])
  const [errors, setErrors] = useState<string[]>([])
  const save = useMutation({
    mutationFn: () => api<Count>('/inventory/counts/', { method: 'POST', body: JSON.stringify({
      warehouse: Number(warehouse), notes,
      lines: lines.map((l) => ({ product: Number(l.product), counted_qty: l.counted_qty })),
    }) }),
    onSuccess: (c) => { void queryClient.invalidateQueries({ queryKey: ['counts'] }); navigate(`/inventory/counts/${c.id}`) },
    onError: (e) => setErrors(e instanceof ApiError ? errorMessages(e.body) : [t('common.loadFailed')]),
  })
  function submit(e: FormEvent) { e.preventDefault(); setErrors([]); save.mutate() }
  return (
    <form onSubmit={submit} className="space-y-4">
      <h3 className="text-lg font-semibold">{t('inventory.newCount')}</h3>
      <p className="text-sm text-slate-600">{t('inventory.countNote')}</p>
      <Card>
        <Field label={t('inventory.warehouse')}>
          <select className={inputClass} value={warehouse} onChange={(e) => setWarehouse(e.target.value)} required aria-label={t('inventory.warehouse')}>
            <option value="">—</option>{warehouses.data?.filter((w) => w.is_active).map((w) => <option key={w.id} value={w.id}>{w.code}</option>)}
          </select>
        </Field>
      </Card>
      <Card title={t('inventory.lines')}><LineEditor lines={lines} onChange={setLines} qtyKey="counted_qty" /></Card>
      <Field label={t('journal.memo')}><input className={inputClass} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={300} /></Field>
      <ErrorList messages={errors} />
      <div className="flex gap-2"><Button type="submit" disabled={save.isPending}>{t('common.save')}</Button><Link className="px-3 py-2 text-sm underline" to="/inventory/counts">{t('common.cancel')}</Link></div>
    </form>
  )
}

export function CountDetail() {
  const { t } = useTranslation()
  const { id } = useParams()
  const { company } = useSession()
  const q = useQuery({ queryKey: ['count', company?.id, id], queryFn: () => api<Count>(`/inventory/counts/${id}/`) })
  if (!q.data) return <Loading query={q} />
  const c = q.data
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">{t('inventory.count')} {c.number}</h3>
      {c.notes && <p className="text-sm text-slate-600">{c.notes}</p>}
      <TableWrap>
        <thead><tr><Th>{t('inventory.product')}</Th><Th end>{t('inventory.bookQty')}</Th><Th end>{t('inventory.countedQty')}</Th><Th end>{t('inventory.difference')}</Th></tr></thead>
        <tbody>
          {c.lines.map((l) => (
            <tr key={l.id}><Td>{l.product_code}</Td><Td end>{formatQty(l.book_qty)}</Td><Td end>{formatQty(l.counted_qty)}</Td><Td end>{formatQty(l.difference)}</Td></tr>
          ))}
        </tbody>
      </TableWrap>
      <Link className="text-sm underline" to="/inventory/counts">{t('common.back')}</Link>
    </div>
  )
}
