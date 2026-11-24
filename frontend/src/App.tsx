import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { api } from './api/client'
import { LANGUAGES, setLanguage } from './i18n'

export default function App() {
  const { t, i18n } = useTranslation()
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api<{ status: string }>('/health/'),
    retry: false,
  })

  return (
    <div className="mx-auto max-w-3xl p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('app.title')}</h1>
        <div className="flex gap-2">
          {LANGUAGES.map((lang) => (
            <button
              key={lang}
              onClick={() => setLanguage(lang)}
              aria-pressed={i18n.language === lang}
              className="rounded border px-3 py-1 aria-pressed:bg-slate-900 aria-pressed:text-white"
            >
              {t(`language.${lang}`)}
            </button>
          ))}
        </div>
      </header>

      <p className="mt-6 text-start">
        {t('health.label')}:{' '}
        <strong>{health.isSuccess ? t('health.ok') : health.isPending ? '…' : t('health.down')}</strong>
      </p>
    </div>
  )
}
