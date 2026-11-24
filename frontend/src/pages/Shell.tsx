import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router'

import { LANGUAGES, setLanguage } from '../i18n'
import { useSession } from '../session'

const NAV = [
  { to: '/journal', key: 'nav.journal', ready: true },
  { to: '/treasury', key: 'nav.treasury', ready: false },
  { to: '/inventory', key: 'nav.inventory', ready: false },
  { to: '/reports', key: 'nav.reports', ready: false },
]

export default function Shell() {
  const { t, i18n } = useTranslation()
  const { user, company, setCompany, logout } = useSession()

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="w-56 shrink-0 bg-slate-900 p-4 text-slate-100">
        <div className="mb-6 text-lg font-semibold">{t('app.title')}</div>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm ${isActive ? 'bg-slate-700' : 'hover:bg-slate-800'} ${item.ready ? '' : 'opacity-60'}`
              }
            >
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-white px-6 py-3">
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
            <span>{user?.username}</span>
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
        <main className="flex-1 p-6">
          {company ? <Outlet /> : <p>{t('shell.noCompany')}</p>}
        </main>
      </div>
    </div>
  )
}
