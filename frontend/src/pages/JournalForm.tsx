import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router'

import { api, ApiError, errorMessages } from '../api/client'
import type { Account, JournalEntry, Partner } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { emptyLine, isBalanced, isBlank, lineProblem, totals, type DraftLine } from '../journal'
import { formatMoney } from '../money'
import { useSession } from '../session'

let keySeq = 0
const nextKey = () => `l${++keySeq}`
const today = () => new Date().toISOString().slice(0, 10)

export default function JournalForm() {
  const { id } = useParams()
  const { t } = useTranslation()
  const { company } = useSession()
  const entry = useQuery({
    queryKey: ['journal-entry', company?.id, id],
    enabled: id !== undefined,
    queryFn: () => api<JournalEntry>(`/journal-entries/${id}/`),
  })
  if (id !== undefined && entry.isError) return <p className="text-red-700">{t('common.loadFailed')}</p>
  if (id !== undefined && !entry.data) return <p>…</p>
  // the editor starts from the loaded entry; a new key resets it for another entry
  return <JournalEditor key={id ?? 'new'} id={id} entry={entry.data ?? null} />
}

function JournalEditor({ id, entry }: { id: string | undefined; entry: JournalEntry | null }) {
  const isNew = entry === null
  const { t, i18n } = useTranslation()
  const { can, company } = useSession()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [date, setDate] = useState(entry?.date ?? today())
  const [description, setDescription] = useState(entry?.description ?? '')
  const [lines, setLines] = useState<DraftLine[]>(() =>
    entry
      ? entry.lines.map((l) => ({
          key: nextKey(),
          account: String(l.account),
          partner: l.partner ? String(l.partner) : '',
          debit: l.debit && Number(l.debit) !== 0 ? l.debit : '',
          credit: l.credit && Number(l.credit) !== 0 ? l.credit : '',
          memo: l.memo ?? '',
        }))
      : [emptyLine(nextKey()), emptyLine(nextKey())],
  )
  const [errors, setErrors] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const [changed, setChanged] = useState(false) // edits not saved yet

  const accounts = useQuery({ queryKey: ['accounts', company?.id], queryFn: () => api<Account[]>('/accounts/') })
  const partners = useQuery({ queryKey: ['partners', company?.id], queryFn: () => api<Partner[]>('/partners/') })

  const english = i18n.language === 'en'
  const accountName = (a: Account) => `${a.code} - ${english && a.name_en ? a.name_en : a.name}`
  const postable = (accounts.data ?? []).filter((a) => a.is_leaf)
  const byId = new Map((accounts.data ?? []).map((a) => [String(a.id), a]))

  const posted = entry?.status === 'posted'
  const linked = !!entry?.source
  const canEdit = !posted && !linked && (isNew ? can('journal.create') : can('journal.edit'))
  const sums = totals(lines)
  const balanced = isBalanced(lines)
  const used = lines.filter((l) => !isBlank(l))
  const problems = used.map(lineProblem)

  function setLine(key: string, patch: Partial<DraftLine>) {
    setChanged(true)
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }

  function payload() {
    return {
      date,
      description,
      lines: used.map((l) => ({
        account: Number(l.account),
        partner: l.partner ? Number(l.partner) : null,
        debit: l.debit.trim() || '0',
        credit: l.credit.trim() || '0',
        memo: l.memo,
      })),
    }
  }

  function fail(err: unknown) {
    setNotice('')
    setErrors(err instanceof ApiError ? errorMessages(err.body) : [t('common.loadFailed')])
  }

  const save = useMutation({
    mutationFn: () =>
      isNew
        ? api<JournalEntry>('/journal-entries/', { method: 'POST', body: JSON.stringify(payload()) })
        : api<JournalEntry>(`/journal-entries/${id}/`, { method: 'PUT', body: JSON.stringify(payload()) }),
    onSuccess: (saved) => {
      setErrors([])
      setChanged(false)
      void queryClient.invalidateQueries({ queryKey: ['journal'] })
      queryClient.setQueryData(['journal-entry', company?.id, String(saved.id)], saved)
      if (isNew) void navigate(`/journal/${saved.id}`, { replace: true })
      else setNotice(t('journal.saved'))
    },
    onError: fail,
  })

  const post = useMutation({
    mutationFn: () => api<JournalEntry>(`/journal-entries/${id}/post/`, { method: 'POST' }),
    onSuccess: (saved) => {
      setErrors([])
      setNotice(t('journal.postedOk'))
      queryClient.setQueryData(['journal-entry', company?.id, id], saved)
      void queryClient.invalidateQueries({ queryKey: ['journal'] })
    },
    onError: fail,
  })

  const remove = useMutation({
    mutationFn: () => api(`/journal-entries/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['journal'] })
      void navigate('/journal')
    },
    onError: fail,
  })

  const dirty = changed
  const canSave = canEdit && description.trim() !== '' && used.length > 0 && problems.every((p) => p === null) && !save.isPending

  return (
    <section className="max-w-5xl space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">{isNew ? t('journal.new') : `${t('journal.entry')} #${id}`}</h2>
        {entry && <Badge tone={posted ? 'green' : 'amber'}>{t(`journal.${entry.status}`)}</Badge>}
        {entry?.is_ai_generated && <Badge tone="slate">{t('journal.ai')}</Badge>}
      </div>

      {linked && !posted && <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">{t(`journal.linked.${entry?.source}`)}</p>}
      {posted && <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">{t('journal.postedLocked')}</p>}

      <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
        <Field label={t('journal.date')}>
          <input type="date" className={inputClass} value={date} onChange={(e) => { setDate(e.target.value); setChanged(true) }} disabled={!canEdit} />
        </Field>
        <Field label={t('journal.description')}>
          <input className={inputClass} value={description} onChange={(e) => { setDescription(e.target.value); setChanged(true) }} disabled={!canEdit} maxLength={500} />
        </Field>
      </div>

      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="p-2 text-start">{t('journal.account')}</th>
              <th className="p-2 text-start">{t('journal.partner')}</th>
              <th className="p-2 text-end">{t('journal.debit')}</th>
              <th className="p-2 text-end">{t('journal.credit')}</th>
              <th className="p-2 text-start">{t('journal.memo')}</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => {
              const account = byId.get(l.account)
              const problem = lineProblem(l)
              return (
                <tr key={l.key} className={`border-t align-top ${problem ? 'bg-red-50' : ''}`}>
                  <td className="p-2 min-w-64">
                    <select className={inputClass} value={l.account} disabled={!canEdit} aria-label={t('journal.account')}
                      onChange={(e) => setLine(l.key, { account: e.target.value, partner: byId.get(e.target.value)?.requires_partner ? l.partner : '' })}>
                      <option value="">—</option>
                      {postable.map((a) => <option key={a.id} value={a.id}>{accountName(a)}</option>)}
                    </select>
                    {problem && <p className="mt-1 text-xs text-red-700">{t(`journal.problem.${problem}`)}</p>}
                  </td>
                  <td className="p-2 min-w-44">
                    <select className={inputClass} value={l.partner} disabled={!canEdit || !account?.requires_partner} aria-label={t('journal.partner')}
                      onChange={(e) => setLine(l.key, { partner: e.target.value })}>
                      <option value="">{account?.requires_partner ? t('journal.choosePartner') : '—'}</option>
                      {(partners.data ?? []).filter((p) => p.is_active).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </td>
                  <td className="p-2 w-32"><input inputMode="decimal" dir="ltr" className={`${inputClass} text-end tabular-nums`} value={l.debit} disabled={!canEdit} aria-label={t('journal.debit')} onChange={(e) => setLine(l.key, { debit: e.target.value })} /></td>
                  <td className="p-2 w-32"><input inputMode="decimal" dir="ltr" className={`${inputClass} text-end tabular-nums`} value={l.credit} disabled={!canEdit} aria-label={t('journal.credit')} onChange={(e) => setLine(l.key, { credit: e.target.value })} /></td>
                  <td className="p-2 min-w-40"><input className={inputClass} value={l.memo} disabled={!canEdit} aria-label={t('journal.memo')} onChange={(e) => setLine(l.key, { memo: e.target.value })} /></td>
                  <td className="p-2">
                    {canEdit && lines.length > 2 && (
                      <button type="button" aria-label={t('journal.removeLine')} className="text-slate-400 hover:text-red-600" onClick={() => { setLines((ls) => ls.filter((x) => x.key !== l.key)); setChanged(true) }}>✕</button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot className="border-t bg-slate-50 font-medium">
            <tr>
              <td className="p-2" colSpan={2}>
                {canEdit && <Button variant="secondary" type="button" onClick={() => { setLines((ls) => [...ls, emptyLine(nextKey())]); setChanged(true) }}>{t('journal.addLine')}</Button>}
              </td>
              <td className="p-2 text-end tabular-nums" data-testid="total-debit">{formatMoney(sums.debit)}</td>
              <td className="p-2 text-end tabular-nums" data-testid="total-credit">{formatMoney(sums.credit)}</td>
              <td className="p-2" colSpan={2}>
                {used.length > 0 && (balanced ? <Badge tone="green">{t('journal.balanced')}</Badge> : <Badge tone="amber">{t('journal.unbalanced', { diff: formatMoney(sums.debit.minus(sums.credit).abs()) })}</Badge>)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {entry && entry.missing_partner_lines > 0 && !posted && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">{t('journal.missingPartner', { count: entry.missing_partner_lines })}</p>
      )}
      <ErrorList messages={errors} />
      {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}

      <div className="flex flex-wrap gap-3">
        {canEdit && <Button disabled={!canSave} onClick={() => save.mutate()}>{isNew ? t('journal.saveDraft') : t('journal.save')}</Button>}
        {!isNew && !posted && can('journal.post') && (
          <Button variant="secondary" disabled={post.isPending || !!dirty || !balanced} onClick={() => post.mutate()} title={dirty ? t('journal.saveFirst') : undefined}>
            {t('journal.post')}
          </Button>
        )}
        {!isNew && !posted && entry?.source !== 'receipt' && can('journal.delete') && (
          <Button variant="danger" disabled={remove.isPending} onClick={() => { if (window.confirm(t('journal.confirmDelete'))) remove.mutate() }}>{t('journal.delete')}</Button>
        )}
        <Button variant="secondary" onClick={() => void navigate('/journal')}>{t('common.back')}</Button>
      </div>
    </section>
  )
}
