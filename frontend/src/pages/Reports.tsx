import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes } from 'react-router'

import { api } from '../api/client'
import type { Account, GeneralLedger, Partner, PartnerStatement, TrialBalance } from '../api/generated'
import { Badge, Field, inputClass } from '../components/ui'
import { BalanceText, Card, Empty, Loading, SubNav, TableWrap, Td, Th } from '../components/common'
import { formatMoney } from '../money'
import { accountLabel, localName } from '../names'
import { useSession } from '../session'

export default function Reports() {
  const { t } = useTranslation()
  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">{t('nav.reports')}</h2>
      <SubNav
        items={[
          { to: '/reports/trial-balance', label: t('report.trialBalance') },
          { to: '/reports/ledger', label: t('report.ledger') },
          { to: '/reports/statement', label: t('report.statement') },
        ]}
      />
      <Routes>
        <Route index element={<Navigate to="trial-balance" replace />} />
        <Route path="trial-balance" element={<TrialBalanceReport />} />
        <Route path="ledger" element={<LedgerReport />} />
        <Route path="statement" element={<StatementReport />} />
      </Routes>
    </section>
  )
}

function useAccounts() {
  const { company } = useSession()
  return useQuery({ queryKey: ['accounts', company?.id], queryFn: () => api<Account[]>('/accounts/') })
}

function usePartners() {
  const { company } = useSession()
  return useQuery({ queryKey: ['partners', company?.id], queryFn: () => api<Partner[]>('/partners/') })
}

function TrialBalanceReport() {
  const { t, i18n } = useTranslation()
  const { company } = useSession()
  const [asOf, setAsOf] = useState('')
  const q = useQuery({
    queryKey: ['trial-balance', company?.id, asOf],
    queryFn: () => api<TrialBalance>(`/reports/trial-balance/${asOf ? `?as_of=${asOf}` : ''}`),
  })
  return (
    <div className="space-y-4">
      <div className="max-w-xs">
        <Field label={t('report.asOf')}>
          <input type="date" className={inputClass} value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </Field>
      </div>
      <Loading query={q} />
      {q.data && (
        <>
          <TableWrap>
            <thead>
              <tr>
                <Th>{t('journal.account')}</Th>
                <Th end>{t('report.movementDebit')}</Th>
                <Th end>{t('report.movementCredit')}</Th>
                <Th end>{t('report.balanceDebit')}</Th>
                <Th end>{t('report.balanceCredit')}</Th>
              </tr>
            </thead>
            <tbody>
              {q.data.rows.map((r) => (
                <tr key={r.account_id}>
                  <Td>{accountLabel(r, i18n.language)}</Td>
                  <Td end>{formatMoney(r.debit)}</Td>
                  <Td end>{formatMoney(r.credit)}</Td>
                  <Td end>{formatMoney(r.balance_debit)}</Td>
                  <Td end>{formatMoney(r.balance_credit)}</Td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 font-semibold">
                <Td>{t('report.total')}</Td>
                <Td end>{formatMoney(q.data.total_debit)}</Td>
                <Td end>{formatMoney(q.data.total_credit)}</Td>
                <Td end>{formatMoney(q.data.total_balance_debit)}</Td>
                <Td end>{formatMoney(q.data.total_balance_credit)}</Td>
              </tr>
            </tfoot>
          </TableWrap>
          <Badge tone={q.data.is_balanced ? 'green' : 'amber'}>
            {q.data.is_balanced ? t('journal.balanced') : t('report.notBalanced')}
          </Badge>
          <p className="text-xs text-slate-500">{t('report.postedOnly')}</p>
        </>
      )}
    </div>
  )
}

function LedgerReport() {
  const { t, i18n } = useTranslation()
  const { company } = useSession()
  const accounts = useAccounts()
  const [account, setAccount] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [status, setStatus] = useState('posted')
  const params = new URLSearchParams({ status })
  if (account) params.set('account', account)
  if (from) params.set('date_from', from)
  if (to) params.set('date_to', to)
  const q = useQuery({
    queryKey: ['ledger', company?.id, params.toString()],
    enabled: !!account,
    queryFn: () => api<GeneralLedger>(`/reports/general-ledger/?${params}`),
  })
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label={t('journal.account')}>
          <select className={inputClass} value={account} onChange={(e) => setAccount(e.target.value)}>
            <option value="">—</option>
            {accounts.data?.map((a) => <option key={a.id} value={a.id}>{accountLabel(a, i18n.language)}</option>)}
          </select>
        </Field>
        <Field label={t('report.from')}><input type="date" className={inputClass} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label={t('report.to')}><input type="date" className={inputClass} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        <Field label={t('journal.status')}>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="posted">{t('report.postedOnlyOption')}</option>
            <option value="all">{t('report.includeDrafts')}</option>
          </select>
        </Field>
      </div>
      {!account && <Empty>{t('report.pickAccount')}</Empty>}
      {account && <Loading query={q} />}
      {q.data?.ledgers.map((l) => (
        <Card key={l.account.id} title={accountLabel(l.account, i18n.language)}>
          {l.is_parent && <p className="mb-2 text-xs text-slate-500">{t('report.parentNote')}</p>}
          <TableWrap>
            <thead>
              <tr>
                <Th>{t('journal.date')}</Th><Th>#</Th><Th>{t('journal.description')}</Th>
                <Th end>{t('journal.debit')}</Th><Th end>{t('journal.credit')}</Th><Th end>{t('report.balance')}</Th>
              </tr>
            </thead>
            <tbody>
              <tr className="bg-slate-50"><Td>{t('report.opening')}</Td><Td /><Td /><Td end /><Td end /><Td end><BalanceText value={l.opening} /></Td></tr>
              {l.rows.map((r, i) => (
                <tr key={i}>
                  <Td className="whitespace-nowrap">{r.date}</Td>
                  <Td>{r.entry_id}</Td>
                  <Td>
                    {r.description}
                    {r.status !== 'posted' && <span className="ms-2"><Badge tone="amber">{t('journal.draft')}</Badge></span>}
                    {r.partner && <span className="ms-2 text-slate-500">{r.partner.name}</span>}
                  </Td>
                  <Td end>{formatMoney(r.debit)}</Td>
                  <Td end>{formatMoney(r.credit)}</Td>
                  <Td end><BalanceText value={r.balance} /></Td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 font-semibold">
                <Td>{t('report.closing')}</Td><Td /><Td />
                <Td end>{formatMoney(l.total_debit)}</Td><Td end>{formatMoney(l.total_credit)}</Td>
                <Td end><BalanceText value={l.closing} /></Td>
              </tr>
            </tfoot>
          </TableWrap>
        </Card>
      ))}
    </div>
  )
}

function StatementReport() {
  const { t, i18n } = useTranslation()
  const { company } = useSession()
  const partners = usePartners()
  const [partner, setPartner] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [status, setStatus] = useState('all')
  const params = new URLSearchParams({ status, partner })
  if (from) params.set('date_from', from)
  if (to) params.set('date_to', to)
  const q = useQuery({
    queryKey: ['statement', company?.id, params.toString()],
    enabled: !!partner,
    queryFn: () => api<PartnerStatement>(`/reports/partner-statement/?${params}`),
  })
  const d = q.data
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label={t('journal.partner')}>
          <select className={inputClass} value={partner} onChange={(e) => setPartner(e.target.value)}>
            <option value="">—</option>
            {partners.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <Field label={t('report.from')}><input type="date" className={inputClass} value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label={t('report.to')}><input type="date" className={inputClass} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        <Field label={t('journal.status')}>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">{t('report.includeDrafts')}</option>
            <option value="posted">{t('report.postedOnlyOption')}</option>
          </select>
        </Field>
      </div>
      {!partner && <Empty>{t('report.pickPartner')}</Empty>}
      {partner && <Loading query={q} />}
      {d && (
        <Card title={d.partner.name}>
          {d.incomplete_entries > 0 && <p className="mb-2 rounded bg-amber-50 p-2 text-sm text-amber-800">{t('report.incompleteNote', { count: d.incomplete_entries })}</p>}
          <TableWrap>
            <thead>
              <tr>
                <Th>{t('journal.date')}</Th><Th>#</Th><Th>{t('journal.description')}</Th><Th>{t('journal.account')}</Th>
                <Th end>{t('journal.debit')}</Th><Th end>{t('journal.credit')}</Th>
                <Th end>{t('report.balancePosted')}</Th><Th end>{t('report.balanceAll')}</Th>
              </tr>
            </thead>
            <tbody>
              <tr className="bg-slate-50"><Td>{t('report.opening')}</Td><Td /><Td /><Td /><Td end /><Td end /><Td end><BalanceText value={d.opening_posted} /></Td><Td end><BalanceText value={d.opening_all} /></Td></tr>
              {d.rows.map((r, i) => (
                <tr key={i}>
                  <Td className="whitespace-nowrap">{r.date}</Td><Td>{r.entry_id}</Td>
                  <Td>{r.description}{r.status !== 'posted' && <span className="ms-2"><Badge tone="amber">{t('journal.draft')}</Badge></span>}</Td>
                  <Td>{localName(r.account, i18n.language)}</Td>
                  <Td end>{formatMoney(r.debit)}</Td><Td end>{formatMoney(r.credit)}</Td>
                  <Td end><BalanceText value={r.balance_posted} /></Td><Td end><BalanceText value={r.balance_all} /></Td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 font-semibold">
                <Td>{t('report.closing')}</Td><Td /><Td /><Td />
                <Td end>{formatMoney(d.posted_debit)}</Td><Td end>{formatMoney(d.posted_credit)}</Td>
                <Td end><BalanceText value={d.closing_posted} /></Td><Td end><BalanceText value={d.closing_all} /></Td>
              </tr>
            </tfoot>
          </TableWrap>
        </Card>
      )}
    </div>
  )
}
