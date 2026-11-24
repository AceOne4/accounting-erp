import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { apiMessages } from '../api/messages'
import { api } from '../api/client'
import type { PaginatedProductList, Product, Unit, Warehouse } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Loading, TableWrap, Td, Th } from '../components/common'
import { localName } from '../names'
import { useSession } from '../sessionContext'


export function Setup() {
  const { t } = useTranslation()
  return (
    <div className="space-y-8">
      <Products />
      <div className="grid gap-6 lg:grid-cols-2">
        <Warehouses />
        <Units />
      </div>
      <p className="text-xs text-slate-500">{t('inventory.setupNote')}</p>
    </div>
  )
}

function Products() {
  const { t, i18n } = useTranslation()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const products = useQuery({ queryKey: ['products', company?.id, q], queryFn: () => api<PaginatedProductList>(`/inventory/products/?q=${encodeURIComponent(q)}`) })
  const units = useQuery({ queryKey: ['units', company?.id], queryFn: () => api<Unit[]>('/inventory/units/') })
  type Draft = { id?: number; code: string; name: string; name_en: string; unit: string; tax_exempt: boolean; tax_rate: string; is_active: boolean }
  const blank: Draft = { code: '', name: '', name_en: '', unit: '', tax_exempt: false, tax_rate: '', is_active: true }
  const [draft, setDraft] = useState<Draft | null>(null)
  const [errors, setErrors] = useState<string[]>([])

  const save = useMutation({
    mutationFn: (d: Draft) => {
      const body = JSON.stringify({ code: d.code, name: d.name, name_en: d.name_en, unit: Number(d.unit), tax_exempt: d.tax_exempt, tax_rate: d.tax_rate || null, is_active: d.is_active })
      return d.id ? api(`/inventory/products/${d.id}/`, { method: 'PUT', body }) : api('/inventory/products/', { method: 'POST', body })
    },
    onSuccess: () => { setDraft(null); setErrors([]); void queryClient.invalidateQueries({ queryKey: ['products'] }); void queryClient.invalidateQueries({ queryKey: ['products-all'] }) },
    onError: (e) => setErrors(apiMessages(e, t)),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/inventory/products/${id}/`, { method: 'DELETE' }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['products'] }),
    onError: (e) => setErrors(apiMessages(e, t)),
  })
  const edit = (p: Product) => { setDraft({ id: p.id, code: p.code, name: p.name, name_en: p.name_en ?? '', unit: String(p.unit), tax_exempt: p.tax_exempt ?? false, tax_rate: p.tax_rate ?? '', is_active: p.is_active ?? true }); setErrors([]) }
  function submit(e: FormEvent) { e.preventDefault(); if (draft) save.mutate(draft) }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{t('inventory.products')}</h3>
        {can('inventory.master') && !draft && <Button onClick={() => { setDraft(blank); setErrors([]) }}>{t('inventory.newProduct')}</Button>}
      </div>
      {draft && (
        <Card title={draft.id ? t('common.edit') : t('inventory.newProduct')}>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
            <Field label={t('common.code')}><input className={inputClass} dir="ltr" value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} required maxLength={50} /></Field>
            <Field label={t('common.name')}><input className={inputClass} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required maxLength={200} /></Field>
            <Field label={t('common.nameEn')}><input className={inputClass} dir="ltr" value={draft.name_en} onChange={(e) => setDraft({ ...draft, name_en: e.target.value })} maxLength={200} /></Field>
            <Field label={t('inventory.unit')}>
              <select className={inputClass} value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} required aria-label={t('inventory.unit')}>
                <option value="">—</option>{units.data?.map((u) => <option key={u.id} value={u.id}>{localName(u, i18n.language)}</option>)}
              </select>
            </Field>
            <Field label={t('inventory.taxRate')}><input className={inputClass} dir="ltr" inputMode="decimal" value={draft.tax_rate} onChange={(e) => setDraft({ ...draft, tax_rate: e.target.value })} disabled={draft.tax_exempt} /></Field>
            <div className="space-y-2 pt-6 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={draft.tax_exempt} onChange={(e) => setDraft({ ...draft, tax_exempt: e.target.checked })} />{t('inventory.taxExempt')}</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />{t('common.active')}</label>
            </div>
            <div className="sm:col-span-3"><ErrorList messages={errors} /></div>
            <div className="flex gap-2 sm:col-span-3"><Button type="submit" disabled={save.isPending}>{t('common.save')}</Button><Button type="button" variant="secondary" onClick={() => setDraft(null)}>{t('common.cancel')}</Button></div>
          </form>
        </Card>
      )}
      {!draft && <ErrorList messages={errors} />}
      <input className={`${inputClass} max-w-xs`} placeholder={t('common.search')} value={q} onChange={(e) => setQ(e.target.value)} />
      <Loading query={products} />
      {products.data && (
        <TableWrap>
          <thead><tr><Th>{t('common.code')}</Th><Th>{t('common.name')}</Th><Th>{t('inventory.unit')}</Th><Th>{t('inventory.taxRate')}</Th><Th /></tr></thead>
          <tbody>
            {products.data.results.map((p) => (
              <tr key={p.id}>
                <Td><span dir="ltr">{p.code}</span></Td><Td>{localName(p, i18n.language)} {!p.is_active && <Badge tone="slate">{t('common.inactive')}</Badge>}</Td>
                <Td>{localName(units.data?.find((u) => u.id === p.unit) ?? { name: '' }, i18n.language)}</Td>
                <Td>{p.tax_exempt ? t('inventory.exempt') : p.tax_rate ? `${p.tax_rate}%` : t('inventory.defaultRate')}</Td>
                <Td className="space-x-3 space-x-reverse text-end">
                  {can('inventory.master') && <button className="underline" onClick={() => edit(p)}>{t('common.edit')}</button>}
                  {can('inventory.master_delete') && <button className="text-red-700 underline" onClick={() => { if (window.confirm(t('inventory.confirmDeleteProduct'))) remove.mutate(p.id) }}>{t('common.delete')}</button>}
                </Td>
              </tr>
            ))}
          </tbody>
        </TableWrap>
      )}
    </div>
  )
}

function Warehouses() {
  const { t, i18n } = useTranslation()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: ['warehouses', company?.id], queryFn: () => api<Warehouse[]>('/inventory/warehouses/') })
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const add = useMutation({
    mutationFn: () => api('/inventory/warehouses/', { method: 'POST', body: JSON.stringify({ code, name }) }),
    onSuccess: () => { setCode(''); setName(''); setErrors([]); void queryClient.invalidateQueries({ queryKey: ['warehouses'] }) },
    onError: (e) => setErrors(apiMessages(e, t)),
  })
  const toggle = useMutation({
    mutationFn: (w: Warehouse) => api(`/inventory/warehouses/${w.id}/`, { method: 'PUT', body: JSON.stringify({ code: w.code, name: w.name, name_en: w.name_en ?? '', is_active: !w.is_active }) }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['warehouses'] }),
  })
  return (
    <Card title={t('inventory.warehouses')}>
      <ul className="mb-3 space-y-1 text-sm">
        {list.data?.map((w) => (
          <li key={w.id} className="flex items-center justify-between"><span><span dir="ltr">{w.code}</span> - {localName(w, i18n.language)} {!w.is_active && <Badge tone="slate">{t('common.inactive')}</Badge>}</span>
            {can('inventory.master') && <button className="text-xs underline" onClick={() => toggle.mutate(w)}>{w.is_active ? t('inventory.deactivate') : t('inventory.activate')}</button>}</li>
        ))}
      </ul>
      {can('inventory.master') && (
        <form onSubmit={(e) => { e.preventDefault(); add.mutate() }} className="grid gap-2 sm:grid-cols-[8rem_1fr_auto]">
          <input className={inputClass} dir="ltr" placeholder={t('common.code')} value={code} onChange={(e) => setCode(e.target.value)} required aria-label={t('common.code')} />
          <input className={inputClass} placeholder={t('common.name')} value={name} onChange={(e) => setName(e.target.value)} required aria-label={t('common.name')} />
          <Button type="submit" disabled={add.isPending}>{t('common.add')}</Button>
        </form>
      )}
      <div className="mt-2"><ErrorList messages={errors} /></div>
    </Card>
  )
}

function Units() {
  const { t, i18n } = useTranslation()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: ['units', company?.id], queryFn: () => api<Unit[]>('/inventory/units/') })
  const [name, setName] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const add = useMutation({
    mutationFn: () => api('/inventory/units/', { method: 'POST', body: JSON.stringify({ name }) }),
    onSuccess: () => { setName(''); setErrors([]); void queryClient.invalidateQueries({ queryKey: ['units'] }) },
    onError: (e) => setErrors(apiMessages(e, t)),
  })
  return (
    <Card title={t('inventory.units')}>
      <ul className="mb-3 space-y-1 text-sm">{list.data?.map((u) => <li key={u.id}>{localName(u, i18n.language)}</li>)}</ul>
      {can('inventory.master') && (
        <form onSubmit={(e) => { e.preventDefault(); add.mutate() }} className="grid gap-2 sm:grid-cols-[1fr_auto]">
          <input className={inputClass} placeholder={t('common.name')} value={name} onChange={(e) => setName(e.target.value)} required aria-label={t('common.name')} />
          <Button type="submit" disabled={add.isPending}>{t('common.add')}</Button>
        </form>
      )}
      <div className="mt-2"><ErrorList messages={errors} /></div>
    </Card>
  )
}
