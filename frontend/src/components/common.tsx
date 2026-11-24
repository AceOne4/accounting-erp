import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'

import { ApiError } from '../api/client'
import { apiMessages } from '../api/messages'
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
    const locked = query.error instanceof ApiError && query.error.status === 423
    return <p role="alert" className={locked ? 'rounded-md bg-amber-50 p-3 text-amber-800' : 'text-red-700'}>{apiMessages(query.error, t).join(' ')}</p>
  }
  if (query.isPending) return <p className="text-slate-500">…</p>
  return null
}

export function Pager({ page, setPage, data }: { page: number; setPage: (p: number) => void; data?: { count: number; next?: string | null; previous?: string | null } }) {
  const { t } = useTranslation()
  if (!data || (!data.next && !data.previous)) return null
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{t('common.count', { count: data.count })}</span>
      <div className="flex gap-2">
        <button className="rounded-md border px-3 py-1 disabled:opacity-50" disabled={!data.previous} onClick={() => setPage(page - 1)}>{t('common.previous')}</button>
        <button className="rounded-md border px-3 py-1 disabled:opacity-50" disabled={!data.next} onClick={() => setPage(page + 1)}>{t('common.next')}</button>
      </div>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed p-6 text-center text-slate-500">{children}</p>
}
