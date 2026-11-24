import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError, errorMessages } from '../api/client'
import type { Account, TypeEnum } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Loading, TableWrap, Td, Th } from '../components/common'
import { localName } from '../names'
import { useSession } from '../session'

const TYPES: TypeEnum[] = ['asset', 'liability', 'equity', 'revenue', 'expense']
type Draft = { id?: number; code: string; name: string; name_en: string; type: TypeEnum; parent: string; is_leaf: boolean; requires_partner: boolean }
const blank: Draft = { code: '', name: '', name_en: '', type: 'asset', parent: '', is_leaf: true, requires_partner: false }

export default function Accounts() {
  const { t, i18n } = useTranslation()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: ['accounts', company?.id], queryFn: () => api<Account[]>('/accounts/') })
  const [draft, setDraft] = useState<Draft | null>(null)
  const [errors, setErrors] = useState<string[]>([])

  const save = useMutation({
    mutationFn: (d: Draft) => {
      const body = JSON.stringify({
        code: d.code, name: d.name, name_en: d.name_en, type: d.type,
        parent: d.parent ? Number(d.parent) : null, is_leaf: d.is_leaf, requires_partner: d.requires_partner,
      })
      return d.id ? api(`/accounts/${d.id}/`, { method: 'PUT', body }) : api('/accounts/', { method: 'POST', body })
    },
    onSuccess: () => { setDraft(null); setErrors([]); void queryClient.invalidateQueries({ queryKey: ['accounts'] }) },
    onError: (e) => setErrors(e instanceof ApiError ? errorMessages(e.body) : [t('common.loadFailed')]),
  })

  const accounts = list.data ?? []
  const byId = new Map(accounts.map((a) => [a.id, a]))
  const depth = (a: Account): number => (a.parent ? 1 + depth(byId.get(a.parent) ?? ({ parent: null } as Account)) : 0)
  const parents = accounts.filter((a) => !a.is_leaf)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (draft) save.mutate(draft)
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t('nav.accounts')}</h2>
        {can('account.manage') && !draft && <Button onClick={() => { setDraft(blank); setErrors([]) }}>{t('accounts.new')}</Button>}
      </div>
      <p className="text-sm text-slate-600">{t('accounts.note')}</p>

      {draft && (
        <Card title={draft.id ? t('accounts.edit') : t('accounts.new')}>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <Field label={t('common.code')}><input className={inputClass} dir="ltr" value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} required maxLength={20} /></Field>
            <Field label={t('accounts.type')}>
              <select className={inputClass} value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value as TypeEnum })}>
                {TYPES.map((k) => <option key={k} value={k}>{t(`accounts.types.${k}`)}</option>)}
              </select>
            </Field>
            <Field label={t('common.name')}><input className={inputClass} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required maxLength={200} /></Field>
            <Field label={t('common.nameEn')}><input className={inputClass} dir="ltr" value={draft.name_en} onChange={(e) => setDraft({ ...draft, name_en: e.target.value })} maxLength={200} /></Field>
            <Field label={t('accounts.parent')}>
              <select className={inputClass} value={draft.parent} onChange={(e) => setDraft({ ...draft, parent: e.target.value })}>
                <option value="">—</option>
                {parents.filter((p) => p.id !== draft.id).map((p) => <option key={p.id} value={p.id}>{p.code} - {localName(p, i18n.language)}</option>)}
              </select>
            </Field>
            <div className="space-y-2 pt-6 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={draft.is_leaf} onChange={(e) => setDraft({ ...draft, is_leaf: e.target.checked })} />{t('accounts.isLeaf')}</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={draft.requires_partner} onChange={(e) => setDraft({ ...draft, requires_partner: e.target.checked })} />{t('accounts.requiresPartner')}</label>
            </div>
            <div className="sm:col-span-2"><ErrorList messages={errors} /></div>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" disabled={save.isPending}>{t('common.save')}</Button>
              <Button type="button" variant="secondary" onClick={() => setDraft(null)}>{t('common.cancel')}</Button>
            </div>
          </form>
        </Card>
      )}

      <Loading query={list} />
      {accounts.length > 0 && (
        <TableWrap>
          <thead><tr><Th>{t('common.code')}</Th><Th>{t('common.name')}</Th><Th>{t('accounts.type')}</Th><Th /></tr></thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className={a.is_leaf ? '' : 'bg-slate-50 font-medium'}>
                <Td><span dir="ltr">{a.code}</span></Td>
                <Td><span style={{ paddingInlineStart: `${depth(a) * 1.25}rem` }}>{localName(a, i18n.language)}</span>{' '}
                  {a.requires_partner && <Badge tone="slate">{t('accounts.partnerBadge')}</Badge>}</Td>
                <Td>{t(`accounts.types.${a.type}`)}</Td>
                <Td end>{can('account.manage') && <button className="underline" onClick={() => { setDraft({ id: a.id, code: a.code, name: a.name, name_en: a.name_en ?? '', type: a.type, parent: a.parent ? String(a.parent) : '', is_leaf: a.is_leaf ?? true, requires_partner: a.requires_partner ?? false }); setErrors([]) }}>{t('common.edit')}</button>}</Td>
              </tr>
            ))}
          </tbody>
        </TableWrap>
      )}
    </section>
  )
}
