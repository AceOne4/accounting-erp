import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'

import { ApiError } from '../api/client'
import type { Balance } from '../api/generated'
import { formatMoney } from '../money'

export function SubNav({ items }: { items: { to: string; label: string }[] }) {
  return (
    <nav className="mb-5 flex flex-wrap gap-2 border-b pb-3">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 hover:bg-slate-100'} border`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function Card({ title, children, className = '' }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border bg-white p-4 ${className}`}>
      {title && <h3 className="mb-3 font-semibold">{title}</h3>}
      {children}
    </div>
  )
}

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto rounded-lg border bg-white"><table className="w-full text-sm">{children}</table></div>
}

export function Th({ children, end = false }: { children?: ReactNode; end?: boolean }) {
  return <th className={`bg-slate-50 p-3 font-medium text-slate-600 ${end ? 'text-end' : 'text-start'}`}>{children}</th>
}

export function Td({ children, end = false, className = '' }: { children?: ReactNode; end?: boolean; className?: string }) {
  return <td className={`border-t p-3 ${end ? 'text-end tabular-nums' : ''} ${className}`}>{children}</td>
}

/** A balance with its side: 1,200.00 Dr / Cr. Zero shows no side. */
export function BalanceText({ value }: { value: Balance }) {
  const { t } = useTranslation()
  const zero = Number(value.amount) === 0
  return (
    <span className="tabular-nums">
      {formatMoney(value.amount)}
      {!zero && value.side ? ` ${t(`report.side.${value.side}`)}` : ''}
    </span>
  )
}

export function Loading({ query }: { query: { isPending: boolean; isError: boolean; error?: unknown } }) {
  const { t } = useTranslation()
  if (query.isError) {
    const e = query.error
    if (e instanceof ApiError && e.status === 423) {
      const b = e.body as { holder?: string; minutes_left?: number }
      return <p role="alert" className="rounded-md bg-amber-50 p-3 text-amber-800">{t('inventory.locked', { holder: b.holder ?? '', minutes: b.minutes_left ?? '' })}</p>
    }
    return <p className="text-red-700">{t('common.loadFailed')}</p>
  }
  if (query.isPending) return <p className="text-slate-500">…</p>
  return null
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed p-6 text-center text-slate-500">{children}</p>
}
