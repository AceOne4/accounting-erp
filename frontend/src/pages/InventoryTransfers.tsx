import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { apiMessages } from '../api/messages'
import { api } from '../api/client'
import type { PaginatedTransferList, Transfer } from '../api/generated'
import { Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Empty, Loading, Pager, TableWrap, Td, Th } from '../components/common'
import { useSession } from '../sessionContext'
import { emptyLine, useWarehouses, type DocLine } from '../inventoryData'
import { LineEditor } from './InventoryDocs'

const today = () => new Date().toISOString().slice(0, 10)

export function TransferList() {
  const { t } = useTranslation()
  const { can, company } = useSession()
  const [page, setPage] = useState(1)
  const list = useQuery({ queryKey: ['transfers', company?.id, page], queryFn: () => api<PaginatedTransferList>(`/inventory/transfers/?page=${page}`) })
  const wh = useWarehouses()
  const code = (id: number) => wh.data?.find((w) => w.id === id)?.code ?? id
  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h3 className="text-lg font-semibold">{t('inventory.transfers')}</h3>
        {can('inventory.transfer') && <Link className="rounded-md bg-slate-900 px-3 py-2 text-sm text-white" to="/inventory/transfers/new">{t('inventory.newTransfer')}</Link>}
      </div>
      <Loading query={list} />
      {list.data && (list.data.results.length === 0 ? <Empty>{t('inventory.noDocs')}</Empty> : (
        <TableWrap>
          <thead><tr><Th>#</Th><Th>{t('journal.date')}</Th><Th>{t('inventory.from')}</Th><Th>{t('inventory.to')}</Th></tr></thead>
          <tbody>
            {list.data.results.map((r) => (
              <tr key={r.id}><Td><Link className="underline" to={`/inventory/transfers/${r.id}`}>{r.number}</Link></Td><Td>{r.date}</Td><Td>{code(r.from_warehouse)}</Td><Td>{code(r.to_warehouse)}</Td></tr>
            ))}
          </tbody>
        </TableWrap>
      ))}
      <Pager page={page} setPage={setPage} data={list.data} />
    </div>
  )
}

export function TransferForm() {
  const { id } = useParams()
  const { company } = useSession()
  const existing = useQuery({ queryKey: ['transfer', company?.id, id], enabled: !!id, queryFn: () => api<Transfer>(`/inventory/transfers/${id}/`) })
  if (id && (existing.isPending || existing.isError)) return <Loading query={existing} />
  return <TransferEditor key={id ?? 'new'} id={id} existing={existing.data} />
}

function TransferEditor({ id, existing }: { id?: string; existing?: Transfer }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { can } = useSession()
  const queryClient = useQueryClient()
  const warehouses = useWarehouses()
  const [date, setDate] = useState(existing?.date ?? today())
  const [from, setFrom] = useState(existing ? String(existing.from_warehouse) : '')
  const [to, setTo] = useState(existing ? String(existing.to_warehouse) : '')
  const [notes, setNotes] = useState(existing?.notes ?? '')
  const [lines, setLines] = useState<DocLine[]>(existing ? existing.lines.map((l) => ({ product: String(l.product), quantity: l.quantity })) : [emptyLine()])
  const [errors, setErrors] = useState<string[]>([])


  const done = () => { void queryClient.invalidateQueries({ queryKey: ['transfers'] }); void queryClient.invalidateQueries({ queryKey: ['stock-levels'] }); navigate('/inventory/transfers') }
  const onError = (e: unknown) => setErrors(apiMessages(e, t))
  const save = useMutation({
    mutationFn: () => api('/inventory/transfers/', { method: 'POST', body: JSON.stringify({
      date, from_warehouse: Number(from), to_warehouse: Number(to), notes,
      lines: lines.map((l) => ({ product: Number(l.product), quantity: l.quantity })),
    }) }),
    onSuccess: done, onError,
  })
  const remove = useMutation({ mutationFn: () => api(`/inventory/transfers/${id}/`, { method: 'DELETE' }), onSuccess: done, onError })
  function submit(e: FormEvent) { e.preventDefault(); setErrors([]); save.mutate() }

  const locked = existing?.locked_reason ?? ''
  const readOnly = !!id // transfers are never edited: delete and re-enter
  const options = warehouses.data?.filter((w) => w.is_active || String(w.id) === from || String(w.id) === to) ?? []
  return (
    <form onSubmit={submit} className="space-y-4">
      <h3 className="text-lg font-semibold">{id ? `${t('inventory.transfer')} ${existing?.number}` : t('inventory.newTransfer')}</h3>
      {locked && <p role="status" className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">{locked}</p>}
      <Card>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label={t('journal.date')}><input type="date" className={inputClass} value={date} disabled={readOnly} onChange={(e) => setDate(e.target.value)} required /></Field>
          <Field label={t('inventory.from')}>
            <select className={inputClass} value={from} disabled={readOnly} onChange={(e) => setFrom(e.target.value)} required aria-label={t('inventory.from')}>
              <option value="">—</option>{options.map((w) => <option key={w.id} value={w.id}>{w.code}</option>)}
            </select>
          </Field>
          <Field label={t('inventory.to')}>
            <select className={inputClass} value={to} disabled={readOnly} onChange={(e) => setTo(e.target.value)} required aria-label={t('inventory.to')}>
              <option value="">—</option>{options.map((w) => <option key={w.id} value={w.id}>{w.code}</option>)}
            </select>
          </Field>
        </div>
      </Card>
      <Card title={t('inventory.lines')}><LineEditor lines={lines} onChange={setLines} readOnly={readOnly} /></Card>
      <Field label={t('journal.memo')}><input className={inputClass} value={notes} disabled={readOnly} onChange={(e) => setNotes(e.target.value)} maxLength={300} /></Field>
      <ErrorList messages={errors} />
      <div className="flex gap-2">
        {!id && can('inventory.transfer') && <Button type="submit" disabled={save.isPending}>{t('common.save')}</Button>}
        {id && !locked && can('inventory.transfer_delete') && (
          <Button type="button" variant="secondary" onClick={() => { if (window.confirm(t('inventory.confirmDelete'))) remove.mutate() }}>{t('common.delete')}</Button>
        )}
        <Link className="px-3 py-2 text-sm underline" to="/inventory/transfers">{t('common.cancel')}</Link>
      </div>
    </form>
  )
}
