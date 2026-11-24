import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { api } from '../api/client'
import type { PaginatedJournalEntryList, StockLevels, TreasuryOverview } from '../api/generated'
import { Card } from '../components/common'
import { formatMoney } from '../money'
import { useSession } from '../sessionContext'

/** The landing page: what needs attention, and shortcuts. Each block shows only if the role may see it. */
export default function Home() {
  const { t } = useTranslation()
  const { company, can } = useSession()
  const drafts = useQuery({
    queryKey: ['home-drafts', company?.id],
    enabled: can('journal.view'),
    queryFn: () => api<PaginatedJournalEntryList>('/journal-entries/?status=draft&page_size=1'),
  })
  const boxes = useQuery({ queryKey: ['treasury', company?.id], enabled: can('treasury.view'), queryFn: () => api<TreasuryOverview>('/treasury/overview/') })
  const stock = useQuery({ queryKey: ['stock-levels', company?.id, ''], enabled: can('inventory.view'), queryFn: () => api<StockLevels>('/inventory/reports/stock-levels/?') })

  return (
    <section className="space-y-5">
      <h2 className="text-xl font-semibold">{company?.name}</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {can('journal.view') && (
          <Card title={t('home.drafts')}>
            <p className="text-3xl font-semibold tabular-nums" data-testid="home-drafts">{drafts.data?.count ?? '…'}</p>
            <Link className="text-sm underline" to="/journal">{t('nav.journal')}</Link>
          </Card>
        )}
        {boxes.data && boxes.data.boxes.map((b) => (
          <Card key={b.code} title={`${b.code} - ${b.name}`}>
            <p className="text-3xl font-semibold tabular-nums">{formatMoney(b.book)}</p>
            <Link className="text-sm underline" to="/treasury">{t('nav.treasury')}</Link>
          </Card>
        ))}
        {stock.data && (
          <Card title={t('inventory.stockValue')}>
            <p className="text-3xl font-semibold tabular-nums">{formatMoney(stock.data.total_value)}</p>
            <Link className="text-sm underline" to="/inventory">{t('nav.inventory')}</Link>
          </Card>
        )}
      </div>
    </section>
  )
}
