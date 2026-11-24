import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router'

import PasswordDialog from '../components/PasswordDialog'
import { LANGUAGES, setLanguage } from '../i18n'
import { useSession } from '../sessionContext'

const NAV = [
  { to: '/', key: 'nav.home', end: true },
  { to: '/journal', key: 'nav.journal' },
  { to: '/partners', key: 'nav.partners' },
  { to: '/accounts', key: 'nav.accounts' },
  { to: '/treasury', key: 'nav.treasury' },
  { to: '/inventory', key: 'nav.inventory' },
  { to: '/reports', key: 'nav.reports' },
  { to: '/users', key: 'nav.users', capability: 'users.manage' },
]

export default function Shell() {
  const { t, i18n } = useTranslation()
  const { user, company, setCompany, logout, can } = useSession()
  const [menu, setMenu] = useState(false)
  const [password, setPassword] = useState(false)

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className={`${menu ? 'block' : 'hidden'} w-56 shrink-0 bg-slate-900 p-4 text-slate-100 md:block print:hidden max-md:fixed max-md:inset-y-0 max-md:start-0 max-md:z-40`}>
        <div className="mb-6 text-lg font-semibold">{t('app.title')}</div>
        <nav className="space-y-1">
          {NAV.filter((item) => !item.capability || can(item.capability)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={'end' in item}
              onClick={() => setMenu(false)}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm ${isActive ? 'bg-slate-700' : 'hover:bg-slate-800'}`
              }
            >
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-white px-4 py-3 md:px-6 print:hidden">
          <button className="rounded border px-2 py-1 text-sm md:hidden" aria-label={t('shell.menu')} aria-expanded={menu} onClick={() => setMenu(!menu)}>☰</button>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">{t('shell.company')}:</span>
            {user && user.companies.length > 1 ? (
              <select
                className="rounded-md border border-slate-300 px-2 py-1"
                value={company?.id}
                onChange={(e) => setCompany(Number(e.target.value))}
                aria-label={t('shell.company')}
              >
                {user.companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            ) : (
              <strong>{company?.name}</strong>
            )}
            {company && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">{t(`role.${company.role}`, company.role)}</span>}
          </div>
          <div className="flex items-center gap-3 text-sm">
            <button className="underline" onClick={() => setPassword(true)}>{user?.username}</button>
            {LANGUAGES.map((lang) => (
              <button
                key={lang}
                onClick={() => setLanguage(lang)}
                aria-pressed={i18n.language === lang}
                className="rounded border px-2 py-0.5 text-xs aria-pressed:bg-slate-900 aria-pressed:text-white"
              >
                {t(`language.${lang}`)}
              </button>
            ))}
            <button onClick={() => void logout()} className="text-slate-600 underline">
              {t('shell.logout')}
            </button>
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6">
          {company ? <Outlet /> : <p>{t('shell.noCompany')}</p>}
        </main>
      </div>
      {password && <PasswordDialog onClose={() => setPassword(false)} />}
    </div>
  )
}
