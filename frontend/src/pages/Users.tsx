import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { apiMessages } from '../api/messages'
import { api } from '../api/client'
import type { Member, RoleEnum } from '../api/generated'
import { Badge, Button, ErrorList, Field, inputClass } from '../components/ui'
import { Card, Loading, TableWrap, Td, Th } from '../components/common'
import { useSession } from '../sessionContext'

const ROLES: RoleEnum[] = ['accountant', 'reviewer', 'chief_accountant', 'system_admin']

export default function Users() {
  const { t } = useTranslation()
  const { company, user } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery({ queryKey: ['users', company?.id], queryFn: () => api<Member[]>('/users/') })
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ username: '', first_name: '', password: '', role: 'accountant' as RoleEnum })
  const [errors, setErrors] = useState<string[]>([])
  const [notice, setNotice] = useState('')

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['users'] })
  const fail = (e: unknown) => { setNotice(''); setErrors(apiMessages(e, t)) }

  const create = useMutation({
    mutationFn: () => api('/users/', { method: 'POST', body: JSON.stringify(form) }),
    onSuccess: () => { setCreating(false); setErrors([]); setForm({ username: '', first_name: '', password: '', role: 'accountant' }); refresh() },
    onError: fail,
  })
  const setRole = useMutation({
    mutationFn: (v: { id: number; role: RoleEnum }) => api(`/users/${v.id}/role/`, { method: 'POST', body: JSON.stringify({ role: v.role }) }),
    onSuccess: () => { setErrors([]); refresh() }, onError: fail,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/users/${id}/`, { method: 'DELETE' }),
    onSuccess: () => { setErrors([]); refresh() }, onError: fail,
  })
  const reset = useMutation({
    mutationFn: (v: { id: number; password: string }) => api(`/users/${v.id}/password/`, { method: 'POST', body: JSON.stringify({ password: v.password }) }),
    onSuccess: () => { setErrors([]); setNotice(t('users.passwordChanged')) }, onError: fail,
  })

  function submit(e: FormEvent) { e.preventDefault(); create.mutate() }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t('nav.users')}</h2>
        {!creating && <Button onClick={() => { setCreating(true); setErrors([]) }}>{t('users.new')}</Button>}
      </div>

      {creating && (
        <Card title={t('users.new')}>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <Field label={t('login.username')}><input className={inputClass} dir="ltr" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required autoComplete="off" /></Field>
            <Field label={t('common.name')}><input className={inputClass} value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></Field>
            <Field label={t('login.password')}><input className={inputClass} type="password" dir="ltr" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required autoComplete="new-password" /></Field>
            <Field label={t('users.role')}>
              <select className={inputClass} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as RoleEnum })}>
                {ROLES.map((r) => <option key={r} value={r}>{t(`role.${r}`)}</option>)}
              </select>
            </Field>
            <div className="sm:col-span-2"><ErrorList messages={errors} /></div>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" disabled={create.isPending}>{t('common.save')}</Button>
              <Button type="button" variant="secondary" onClick={() => setCreating(false)}>{t('common.cancel')}</Button>
            </div>
          </form>
        </Card>
      )}
      {!creating && <ErrorList messages={errors} />}
      {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}

      <Loading query={list} />
      {list.data && (
        <TableWrap>
          <thead><tr><Th>{t('login.username')}</Th><Th>{t('common.name')}</Th><Th>{t('users.role')}</Th><Th /></tr></thead>
          <tbody>
            {list.data.map((m) => {
              const me = m.username === user?.username
              return (
                <tr key={m.id}>
                  <Td><span dir="ltr">{m.username}</span> {me && <Badge tone="slate">{t('users.you')}</Badge>}</Td>
                  <Td>{m.first_name}</Td>
                  <Td>
                    <select className={`${inputClass} max-w-48`} value={m.role} disabled={me} aria-label={t('users.role')}
                      onChange={(e) => setRole.mutate({ id: m.id, role: e.target.value as RoleEnum })}>
                      {ROLES.map((r) => <option key={r} value={r}>{t(`role.${r}`)}</option>)}
                    </select>
                  </Td>
                  <Td className="space-x-3 space-x-reverse text-end">
                    <button className="underline" onClick={() => { const password = window.prompt(t('users.newPassword')); if (password) reset.mutate({ id: m.id, password }) }}>{t('users.resetPassword')}</button>
                    {!me && <button className="text-red-700 underline" onClick={() => { if (window.confirm(t('users.confirmRemove'))) remove.mutate(m.id) }}>{t('users.remove')}</button>}
                  </Td>
                </tr>
              )
            })}
          </tbody>
        </TableWrap>
      )}
    </section>
  )
}
