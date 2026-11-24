import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Route, Routes } from 'react-router'

import { api } from '../api/client'
import { SubNav } from '../components/common'
import { Button } from '../components/ui'
import { useSession } from '../sessionContext'
import { CountDetail, CountForm, CountList } from './InventoryCounts'
import { ItemCard, StockLevels } from './InventoryReports'
import { ReceiptForm, ReceiptList } from './InventoryReceipts'
import { Setup } from './InventorySetup'
import { TransferForm, TransferList } from './InventoryTransfers'

let releaseTimer: ReturnType<typeof setTimeout> | undefined

export default function Inventory() {
  const { t } = useTranslation()
  const { company } = useSession()

  // Only one person at a time works in inventory. Leaving the module frees the lock.
  // The release waits a moment so a quick re-mount (React StrictMode in development) cancels it.
  useEffect(() => {
    if (releaseTimer) clearTimeout(releaseTimer)
    return () => {
      releaseTimer = setTimeout(() => void api('/inventory/lock/release/', { method: 'POST' }).catch(() => undefined), 300)
    }
  }, [company?.id])

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t('nav.inventory')}</h2>
        <Button variant="secondary" onClick={() => void api('/inventory/lock/release/', { method: 'POST' }).then(() => window.history.back())}>{t('inventory.leave')}</Button>
      </div>
      <SubNav
        items={[
          { to: '/inventory/levels', label: t('inventory.levels') },
          { to: '/inventory/card', label: t('inventory.card') },
          { to: '/inventory/receipts', label: t('inventory.receipts') },
          { to: '/inventory/transfers', label: t('inventory.transfers') },
          { to: '/inventory/counts', label: t('inventory.counts') },
          { to: '/inventory/setup', label: t('inventory.setup') },
        ]}
      />
      <Routes>
        <Route index element={<Navigate to="levels" replace />} />
        <Route path="levels" element={<StockLevels />} />
        <Route path="card" element={<ItemCard />} />
        <Route path="receipts" element={<ReceiptList />} />
        <Route path="receipts/new" element={<ReceiptForm />} />
        <Route path="receipts/:id" element={<ReceiptForm />} />
        <Route path="transfers" element={<TransferList />} />
        <Route path="transfers/new" element={<TransferForm />} />
        <Route path="transfers/:id" element={<TransferForm />} />
        <Route path="counts" element={<CountList />} />
        <Route path="counts/new" element={<CountForm />} />
        <Route path="counts/:id" element={<CountDetail />} />
        <Route path="setup" element={<Setup />} />
      </Routes>
    </section>
  )
}
