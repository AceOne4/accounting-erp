import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Decimal from 'decimal.js'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { apiMessages } from '../api/messages'
import { api } from '../api/client'
import type { Account, CashCount, PaginatedCashCountList, Partner, TreasuryOverview, VoucherKindEnum, VoucherResult } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Empty, Loading, Pager, TableWrap, Td, Th } from '../components/common'
import { formatMoney } from '../money'
import { accountLabel } from '../names'
import { useSession } from '../sessionContext'

const KINDS: { kind: VoucherKindEnum; partner: 'customer' | 'supplier' | null; account?: boolean }[] = [
  { kind: 'collect', partner: 'customer' },
  { kind: 'refund', partner: 'customer' },
  { kind: 'deposit', partner: null },
  { kind: 'fund', partner: null },
  { kind: 'expense', partner: null, account: true },
  { kind: 'supplier', partner: 'supplier' },
]
const today = () => new Date().toISOString().slice(0, 10)

export default function Treasury() {
  const { t } = useTranslation()
  const { company } = useSession()
  const overview = useQuery({ queryKey: ['treasury', company?.id], queryFn: () => api<TreasuryOverview>('/treasury/overview/') })
  return (
    <section className="space-y-6">
      <h2 className="text-xl font-semibold">{t('nav.treasury')}</h2>
      <Loading query={overview} />
      {overview.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            {overview.data.boxes.map((b) => (
              <Card key={b.code} title={`${b.code} - ${b.name}`}>
                <dl className="space-y-1 text-sm">
                  <div className="flex justify-between"><dt>{t('treasury.posted')}</dt><dd className="tabular-nums">{formatMoney(b.posted)}</dd></div>
                  <div className="flex justify-between"><dt>{t('treasury.pending')}</dt><dd className="tabular-nums">{formatMoney(b.pending)}</dd></div>
                  <div className="flex justify-between border-t pt-1 font-semibold"><dt>{t('treasury.book')}</dt><dd className="tabular-nums" data-testid={`book-${b.code}`}>{formatMoney(b.book)}</dd></div>
                </dl>
              </Card>
            ))}
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <VoucherForm />
            <CashCountForm overview={overview.data} />
          </div>
          <CashCountHistory />
          <Card title={t('treasury.recent')}>
            {overview.data.recent_entries.length === 0 ? <Empty>{t('journal.empty')}</Empty> : (
              <TableWrap>
                <thead><tr><Th>#</Th><Th>{t('journal.date')}</Th><Th>{t('journal.description')}</Th><Th>{t('journal.status')}</Th></tr></thead>
                <tbody>
                  {overview.data.recent_entries.map((e) => (
                    <tr key={e.id}><Td><Link className="underline" to={`/journal/${e.id}`}>{e.id}</Link></Td><Td>{e.date}</Td><Td>{e.description}</Td>
                      <Td><Badge tone={e.status === 'posted' ? 'green' : 'amber'}>{t(`journal.${e.status}`)}</Badge></Td></tr>
                  ))}
                </tbody>
              </TableWrap>
            )}
          </Card>
        </>
      )}
    </section>
  )
}

function VoucherForm() {
  const { t, i18n } = useTranslation()
  const { can, company } = useSession()
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<VoucherKindEnum>('collect')
  const [date, setDate] = useState(today())
  const [amount, setAmount] = useState('')
  const [partner, setPartner] = useState('')
  const [expense, setExpense] = useState('')
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const [postNow, setPostNow] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [result, setResult] = useState<VoucherResult | null>(null)

  const cfg = KINDS.find((k) => k.kind === kind)!
  const partners = useQuery({ queryKey: ['partners', company?.id], queryFn: () => api<Partner[]>('/partners/'), enabled: !!cfg.partner })
  const accounts = useQuery({ queryKey: ['accounts', company?.id], queryFn: () => api<Account[]>('/accounts/'), enabled: !!cfg.account })
  const eligible = (partners.data ?? []).filter((p) => p.is_active && (p.kind === 'both' || p.kind === cfg.partner))
  const expenseAccounts = (accounts.data ?? []).filter((a) => a.type === 'expense' && a.is_leaf)

  const create = useMutation({
    mutationFn: () => api<VoucherResult>('/treasury/vouchers/', {
      method: 'POST',
      body: JSON.stringify({
        kind, date, amount, partner: cfg.partner && partner ? Number(partner) : null,
        expense_account: cfg.account && expense ? Number(expense) : null, reference, note, post_now: postNow,
      }),
    }),
    onSuccess: (r) => { setErrors([]); setResult(r); setPostNow(false); setAmount(''); setReference(''); setNote(''); void queryClient.invalidateQueries({ queryKey: ['treasury'] }) },
    onError: (e) => { setResult(null); setErrors(apiMessages(e, t)) },
  })
  function submit(e: FormEvent) { e.preventDefault(); setResult(null); create.mutate() }

  if (!can('treasury.voucher')) return null
  return (
    <Card title={t('treasury.voucher')}>
      <form onSubmit={submit} className="space-y-3">
        <Field label={t('treasury.operation')}>
          <select className={inputClass} value={kind} onChange={(e) => { setKind(e.target.value as VoucherKindEnum); setPartner(''); setExpense('') }}>
            {KINDS.map((k) => <option key={k.kind} value={k.kind}>{t(`treasury.kinds.${k.kind}`)}</option>)}
          </select>
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('journal.date')}><input type="date" className={inputClass} value={date} onChange={(e) => setDate(e.target.value)} required /></Field>
          <Field label={t('treasury.amount')}><input inputMode="decimal" dir="ltr" className={`${inputClass} text-end`} value={amount} onChange={(e) => setAmount(e.target.value)} required aria-label={t('treasury.amount')} /></Field>
        </div>
        {cfg.partner && (
          <Field label={t('journal.partner')}>
            <select className={inputClass} value={partner} onChange={(e) => setPartner(e.target.value)} required aria-label={t('journal.partner')}>
              <option value="">—</option>
              {eligible.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
        )}
        {cfg.account && (
          <Field label={t('treasury.expenseAccount')}>
            <select className={inputClass} value={expense} onChange={(e) => setExpense(e.target.value)} required aria-label={t('treasury.expenseAccount')}>
              <option value="">—</option>
              {expenseAccounts.map((a) => <option key={a.id} value={a.id}>{accountLabel(a, i18n.language)}</option>)}
            </select>
          </Field>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('treasury.reference')}><input className={inputClass} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={100} /></Field>
          <Field label={t('journal.memo')}><input className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></Field>
        </div>
        {can('journal.post') && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={postNow} onChange={(e) => setPostNow(e.target.checked)} />{t('treasury.postNow')}</label>}
        <ErrorList messages={errors} />
        {result && (
          <p role="status" className="text-sm text-emerald-700">
            {result.posted ? t('treasury.savedPosted') : result.post_error ? t('treasury.savedPostFailed', { error: result.post_error }) : t('treasury.savedDraft')}{' '}
            <Link className="underline" to={`/journal/${result.entry_id}`}>#{result.entry_id}</Link>
          </p>
        )}
        <Button type="submit" disabled={create.isPending}>{t('common.save')}</Button>
      </form>
    </Card>
  )
}

function CashCountForm({ overview }: { overview: TreasuryOverview }) {
  const { t } = useTranslation()
  const { can } = useSession()
  const queryClient = useQueryClient()
  const boxes = overview.boxes.filter((b) => b.code === '1011' || b.code === '1012')
  const [box, setBox] = useState(String(boxes[0]?.account ?? ''))
  const [qty, setQty] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState('')
  const [adjust, setAdjust] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [saved, setSaved] = useState<CashCount | null>(null)

  const total = overview.denominations.reduce((sum, d) => sum.plus(new Decimal(d).times(Number(qty[d]) || 0)), new Decimal(0))
  const book = new Decimal(boxes.find((b) => String(b.account) === box)?.book ?? 0)
  const diff = total.minus(book)

  const save = useMutation({
    mutationFn: () => api<CashCount>('/treasury/cash-counts/', {
      method: 'POST',
      body: JSON.stringify({
        box: Number(box), notes, adjust,
        quantities: Object.fromEntries(overview.denominations.map((d) => [d, Math.max(0, Math.trunc(Number(qty[d]) || 0))])),
      }),
    }),
    onSuccess: (c) => { setErrors([]); setSaved(c); setQty({}); setNotes(''); setAdjust(false); void queryClient.invalidateQueries({ queryKey: ['treasury'] }) },
    onError: (e) => { setSaved(null); setErrors(apiMessages(e, t)) },
  })

  if (!can('treasury.count')) return null
  return (
    <Card title={t('treasury.cashCount')}>
      <form onSubmit={(e) => { e.preventDefault(); save.mutate() }} className="space-y-3">
        <Field label={t('treasury.box')}>
          <select className={inputClass} value={box} onChange={(e) => setBox(e.target.value)} aria-label={t('treasury.box')}>
            {boxes.map((b) => <option key={b.account} value={b.account}>{b.code} - {b.name}</option>)}
          </select>
        </Field>
        <div className="grid grid-cols-3 gap-2">
          {overview.denominations.map((d) => (
            <label key={d} className="text-sm">
              <span className="mb-1 block text-slate-600" dir="ltr">{d}</span>
              <input inputMode="numeric" dir="ltr" className={`${inputClass} text-end`} value={qty[d] ?? ''} aria-label={`${t('treasury.denomination')} ${d}`}
                onChange={(e) => setQty({ ...qty, [d]: e.target.value.replace(/\D/g, '') })} />
            </label>
          ))}
        </div>
        <dl className="space-y-1 rounded-md bg-slate-50 p-3 text-sm">
          <div className="flex justify-between"><dt>{t('treasury.counted')}</dt><dd className="tabular-nums" data-testid="counted-total">{formatMoney(total)}</dd></div>
          <div className="flex justify-between"><dt>{t('treasury.book')}</dt><dd className="tabular-nums">{formatMoney(book)}</dd></div>
          <div className="flex justify-between border-t pt-1 font-semibold"><dt>{t('treasury.difference')}</dt><dd className="tabular-nums" data-testid="count-diff">{formatMoney(diff)}</dd></div>
        </dl>
        <Field label={t('journal.memo')}><input className={inputClass} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={300} /></Field>
        {can('journal.create') && !diff.isZero() && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={adjust} onChange={(e) => setAdjust(e.target.checked)} />{t('treasury.adjust')}</label>}
        <ErrorList messages={errors} />
        {saved && <p role="status" className="text-sm text-emerald-700">{t('treasury.countSaved', { diff: formatMoney(saved.difference) })}</p>}
        <Button type="submit" disabled={save.isPending}>{t('treasury.saveCount')}</Button>
      </form>
    </Card>
  )
}

function CashCountHistory() {
  const { t } = useTranslation()
  const { company } = useSession()
  const [page, setPage] = useState(1)
  const q = useQuery({ queryKey: ['treasury', company?.id, 'counts', page], queryFn: () => api<PaginatedCashCountList>(`/treasury/cash-counts/?page=${page}`) })
  if (!q.data || q.data.results.length === 0) return null
  return (
    <Card title={t('treasury.history')}>
      <TableWrap>
        <thead><tr><Th>{t('journal.date')}</Th><Th>{t('treasury.box')}</Th><Th end>{t('treasury.counted')}</Th><Th end>{t('treasury.book')}</Th><Th end>{t('treasury.difference')}</Th><Th>{t('treasury.by')}</Th></tr></thead>
        <tbody>
          {q.data.results.map((c) => (
            <tr key={c.id}><Td>{c.count_date}</Td><Td>{c.box_code}</Td><Td end>{formatMoney(c.counted_total)}</Td><Td end>{formatMoney(c.book_balance)}</Td><Td end>{formatMoney(c.difference)}</Td><Td>{c.counted_by}</Td></tr>
          ))}
        </tbody>
      </TableWrap>
      <Pager page={page} setPage={setPage} data={q.data} />
    </Card>
  )
}
