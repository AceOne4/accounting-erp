import { createContext, useContext } from 'react'

import type { CompanyRole, Me } from './api/generated'

export type Session = {
  user: Me | null
  loading: boolean
  company: CompanyRole | null
  setCompany: (id: number) => void
  can: (capability: string) => boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const SessionContext = createContext<Session | null>(null)

export function useSession(): Session {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside SessionProvider')
  return ctx
}
