import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, ApiError, setCompanyId } from './api/client'
import type { Me } from './api/generated'
import { SessionContext, type Session } from './sessionContext'

const COMPANY_KEY = 'erp.company'

function savedCompany(): number | null {
  try {
    const raw = localStorage.getItem(COMPANY_KEY)
    return raw ? Number(raw) : null
  } catch {
    return null
  }
}


export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [companyId, setCompanyIdState] = useState<number | null>(savedCompany)

  const me = useQuery({
    queryKey: ['me'],
    retry: false,
    queryFn: async (): Promise<Me | null> => {
      await api('/auth/csrf/') // makes sure the csrftoken cookie exists
      try {
        return await api<Me>('/me/')
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return null
        throw e
      }
    },
  })

  const user = me.data ?? null
  const company = useMemo(() => {
    if (!user || user.companies.length === 0) return null
    return user.companies.find((c) => c.id === companyId) ?? user.companies[0]
  }, [user, companyId])

  // every request acts in the selected company
  useEffect(() => {
    setCompanyId(company?.id ?? null)
  }, [company])

  const setCompany = useCallback(
    (id: number) => {
      try {
        localStorage.setItem(COMPANY_KEY, String(id))
      } catch {
        // ignore
      }
      setCompanyIdState(id)
      setCompanyId(id)
      // anything cached belongs to the previous company
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    },
    [queryClient],
  )

  const login = useCallback(
    async (username: string, password: string) => {
      await api('/auth/csrf/')
      await api('/auth/login/', { method: 'POST', body: JSON.stringify({ username, password }) })
      await queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    await api('/auth/logout/', { method: 'POST' })
    queryClient.clear()
    await queryClient.invalidateQueries({ queryKey: ['me'] })
  }, [queryClient])

  const can = useCallback((capability: string) => !!company?.capabilities.includes(capability), [company])

  const value: Session = { user, loading: me.isPending, company, setCompany, can, login, logout }
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
