import { createContext, useContext } from 'react'

import type { Me, Membership, TokenResponse } from '@/lib/types'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export type AuthContextValue = {
  status: AuthStatus
  me: Me | null
  /** The clinic the user is currently working in (null if they have none yet). */
  membership: Membership | null
  /** Call with the response of login/register/reset-password/accept-invite. */
  signIn: (tokens: TokenResponse) => Promise<void>
  signOut: (everywhere?: boolean) => Promise<void>
  switchClinic: (clinicId: string) => void
  reloadMe: () => Promise<Me | null>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
