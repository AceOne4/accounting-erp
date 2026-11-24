import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { api } from '../api/client'
import type { PaginatedJournalEntryList } from '../api/generated'
import { Badge, Button, inputClass } from '../components/ui'
import { formatMoney } from '../money'
import { useSession } from '../sessionContext'

export default function JournalList() {
  const { t } = useTranslation()
  const { can, company } = useSession()
  const [status, setStatus] = useState('')
  const [incomplete, setIncomplete] = useState(false)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)

  const params = new URLSearchParams({ page: String(page) })
  if (status) params.set('status', status)
  if (incomplete) params.set('incomplete', '1')
  if (q.trim()) params.set('q', q.trim())

  const list = useQuery({
    queryKey: ['journal', company?.id, params.toString()],
    queryFn: () => api<PaginatedJournalEntryList>(`/journal-entries/?${params}`),
  })

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t('journal.title')}</h2>
        {can('journal.create') && (
          <Link to="/journal/new">
            <Button>{t('journal.new')}</Button>
          </Link>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <input className={`${inputClass} max-w-xs`} placeholder={t('journal.search')} value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} />
        <select className={`${inputClass} max-w-40`} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label={t('journal.status')}>
          <option value="">{t('journal.allStatuses')}</option>
          <option value="draft">{t('journal.draft')}</option>
          <option value="posted">{t('journal.posted')}</option>
        </select>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={incomplete} onChange={(e) => { setIncomplete(e.target.checked); setPage(1) }} />
          {t('journal.onlyIncomplete')}
        </label>
      </div>

      {list.isError && <p className="text-red-700">{t('common.loadFailed')}</p>}
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-start text-slate-600">
            <tr>
              <th className="p-3 text-start">#</th>
              <th className="p-3 text-start">{t('journal.date')}</th>
              <th className="p-3 text-start">{t('journal.description')}</th>
              <th className="p-3 text-end">{t('journal.debit')}</th>
              <th className="p-3 text-end">{t('journal.credit')}</th>
              <th className="p-3 text-start">{t('journal.status')}</th>
            </tr>
          </thead>
          <tbody>
            {list.data?.results.map((e) => (
              <tr key={e.id} className="border-t hover:bg-slate-50">
                <td className="p-3"><Link className="underline" to={`/journal/${e.id}`}>{e.id}</Link></td>
                <td className="p-3 whitespace-nowrap">{e.date}</td>
                <td className="p-3">{e.description}</td>
                <td className="p-3 text-end tabular-nums">{formatMoney(e.total_debit)}</td>
                <td className="p-3 text-end tabular-nums">{formatMoney(e.total_credit)}</td>
                <td className="p-3 space-x-2 space-x-reverse">
                  <Badge tone={e.status === 'posted' ? 'green' : 'amber'}>{t(`journal.${e.status}`)}</Badge>
                  {e.missing_partner_lines > 0 && <Badge tone="slate">{t('journal.incomplete')}</Badge>}
                </td>
              </tr>
            ))}
            {list.data?.results.length === 0 && (
              <tr><td colSpan={6} className="p-6 text-center text-slate-500">{t('journal.empty')}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span>{list.data ? t('common.count', { count: list.data.count }) : ''}</span>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={!list.data?.previous} onClick={() => setPage((p) => p - 1)}>{t('common.previous')}</Button>
          <Button variant="secondary" disabled={!list.data?.next} onClick={() => setPage((p) => p + 1)}>{t('common.next')}</Button>
        </div>
      </div>
    </section>
  )
}
