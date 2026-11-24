import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { Button, ErrorList, Field, inputClass } from '../components/ui'
import { LANGUAGES, setLanguage } from '../i18n'
import { useSession } from '../session'

export default function Login() {
  const { t, i18n } = useTranslation()
  const { login } = useSession()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErrors([])
    try {
      await login(username, password)
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setErrors([t('login.tooMany')])
      else if (err instanceof ApiError && typeof err.body === 'object' && err.body !== null && err.status < 500)
        setErrors([t('login.wrong')]) // a JSON error from the API itself
      else setErrors([t('login.down')]) // HTML error pages (e.g. CSRF), 5xx or no connection
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">{t('app.title')}</h1>
          <div className="flex gap-1">
            {LANGUAGES.map((lang) => (
              <button
                type="button"
                key={lang}
                onClick={() => setLanguage(lang)}
                aria-pressed={i18n.language === lang}
                className="rounded border px-2 py-0.5 text-xs aria-pressed:bg-slate-900 aria-pressed:text-white"
              >
                {t(`language.${lang}`)}
              </button>
            ))}
          </div>
        </div>
        <Field label={t('login.username')}>
          <input className={inputClass} value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" required />
        </Field>
        <Field label={t('login.password')}>
          <input className={inputClass} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </Field>
        <ErrorList messages={errors} />
        <Button type="submit" className="w-full" disabled={busy}>
          {t('login.submit')}
        </Button>
      </form>
    </div>
  )
}
