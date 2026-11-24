import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { apiMessages } from '../api/messages'
import { api } from '../api/client'
import type { Partner, PartnerKindEnum } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Empty, Loading, TableWrap, Td, Th } from '../components/common'
import { useSession } from '../sessionContext'

const KINDS: PartnerKindEnum[] = ['customer', 'supplier', 'both']
type Draft = { id?: number; name: string; kind: PartnerKindEnum; tax_id: string; phone: string; is_active: boolean }
const blank: Draft = { name: '', kind: 'customer', tax_id: '', phone: '', is_active: true }

export default function Partners() {
  const { t } = useTranslation()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: ['partners', company?.id], queryFn: () => api<Partner[]>('/partners/') })
  const [draft, setDraft] = useState<Draft | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [filter, setFilter] = useState('')

  const save = useMutation({
    mutationFn: (d: Draft) => {
      const body = JSON.stringify({ name: d.name, kind: d.kind, tax_id: d.tax_id, phone: d.phone, is_active: d.is_active })
      return d.id ? api(`/partners/${d.id}/`, { method: 'PUT', body }) : api('/partners/', { method: 'POST', body })
    },
    onSuccess: () => { setDraft(null); setErrors([]); void queryClient.invalidateQueries({ queryKey: ['partners'] }) },
    onError: (e) => setErrors(apiMessages(e, t)),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/partners/${id}/`, { method: 'DELETE' }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['partners'] }),
    onError: (e) => setErrors(apiMessages(e, t)),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (draft) save.mutate(draft)
  }
  const rows = (list.data ?? []).filter((p) => p.name.toLowerCase().includes(filter.toLowerCase()))

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t('nav.partners')}</h2>
        {can('partner.edit') && !draft && <Button onClick={() => { setDraft(blank); setErrors([]) }}>{t('partners.new')}</Button>}
      </div>

      {draft && (
        <Card title={draft.id ? t('partners.edit') : t('partners.new')}>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <Field label={t('common.name')}><input className={inputClass} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required maxLength={200} /></Field>
            <Field label={t('partners.kind')}>
              <select className={inputClass} value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as PartnerKindEnum })}>
                {KINDS.map((k) => <option key={k} value={k}>{t(`partners.kinds.${k}`)}</option>)}
              </select>
            </Field>
            <Field label={t('partners.taxId')}><input className={inputClass} value={draft.tax_id} onChange={(e) => setDraft({ ...draft, tax_id: e.target.value })} maxLength={30} /></Field>
            <Field label={t('partners.phone')}><input className={inputClass} dir="ltr" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} maxLength={30} /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />{t('common.active')}</label>
            <div className="sm:col-span-2"><ErrorList messages={errors} /></div>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" disabled={save.isPending}>{t('common.save')}</Button>
              <Button type="button" variant="secondary" onClick={() => setDraft(null)}>{t('common.cancel')}</Button>
            </div>
          </form>
        </Card>
      )}
      {!draft && <ErrorList messages={errors} />}

      <input className={`${inputClass} max-w-xs`} placeholder={t('common.search')} value={filter} onChange={(e) => setFilter(e.target.value)} />
      <Loading query={list} />
      {list.data && rows.length === 0 && <Empty>{t('partners.empty')}</Empty>}
      {rows.length > 0 && (
        <TableWrap>
          <thead><tr><Th>{t('common.name')}</Th><Th>{t('partners.kind')}</Th><Th>{t('partners.taxId')}</Th><Th>{t('partners.phone')}</Th><Th /></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <Td>{p.name} {!p.is_active && <Badge tone="slate">{t('common.inactive')}</Badge>}</Td>
                <Td>{t(`partners.kinds.${p.kind}`)}</Td>
                <Td>{p.tax_id}</Td>
                <Td><span dir="ltr">{p.phone}</span></Td>
                <Td className="space-x-3 space-x-reverse text-end">
                  {can('partner.edit') && <button className="underline" onClick={() => { setDraft({ id: p.id, name: p.name, kind: p.kind, tax_id: p.tax_id ?? '', phone: p.phone ?? '', is_active: p.is_active ?? true }); setErrors([]) }}>{t('common.edit')}</button>}
                  {can('partner.delete') && <button className="text-red-700 underline" onClick={() => { if (window.confirm(t('partners.confirmDelete'))) remove.mutate(p.id) }}>{t('common.delete')}</button>}
                </Td>
              </tr>
            ))}
          </tbody>
        </TableWrap>
      )}
    </section>
  )
}
