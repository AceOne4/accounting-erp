import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../api/client'
import { apiMessages } from '../api/messages'
import { Button, ErrorList, Field, inputClass } from './ui'

export default function PasswordDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const save = useMutation({
    mutationFn: () => api('/auth/password/', { method: 'POST', body: JSON.stringify({ current_password: current, new_password: next }) }),
    onSuccess: () => { setErrors([]); setDone(true) },
    onError: (e) => setErrors(apiMessages(e, t)),
  })
  function submit(e: FormEvent) {
    e.preventDefault()
    if (next !== again) { setErrors([t('password.mismatch')]); return }
    save.mutate()
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 print:hidden" role="dialog" aria-modal="true" aria-label={t('password.title')}>
      <form onSubmit={submit} className="w-full max-w-sm space-y-3 rounded-lg bg-white p-5">
        <h2 className="text-lg font-semibold">{t('password.title')}</h2>
        {done ? <p role="status" className="text-emerald-700">{t('users.passwordChanged')}</p> : (
          <>
            <Field label={t('password.current')}><input type="password" dir="ltr" className={inputClass} value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" /></Field>
            <Field label={t('password.new')}><input type="password" dir="ltr" className={inputClass} value={next} onChange={(e) => setNext(e.target.value)} required autoComplete="new-password" /></Field>
            <Field label={t('password.again')}><input type="password" dir="ltr" className={inputClass} value={again} onChange={(e) => setAgain(e.target.value)} required autoComplete="new-password" /></Field>
            <ErrorList messages={errors} />
          </>
        )}
        <div className="flex gap-2">
          {!done && <Button type="submit" disabled={save.isPending}>{t('common.save')}</Button>}
          <Button type="button" variant="secondary" onClick={onClose}>{done ? t('common.back') : t('common.cancel')}</Button>
        </div>
      </form>
    </div>
  )
}
