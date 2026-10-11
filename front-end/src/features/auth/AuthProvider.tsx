import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { api, refreshAccessToken, setAccessToken, setClinicId } from '@/lib/api'
import type { Me, TokenResponse } from '@/lib/types'

import { AuthContext, type AuthStatus } from './auth-context'

const CLINIC_STORAGE_KEY = 'doctoo.clinicId'

function readStoredClinicId(): string | null {
  try {
    return localStorage.getItem(CLINIC_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeClinicId(id: string | null) {
  try {
    if (id) localStorage.setItem(CLINIC_STORAGE_KEY, id)
    else localStorage.removeItem(CLINIC_STORAGE_KEY)
  } catch {
    // storage unavailable (private mode); the choice just won't be remembered
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [me, setMe] = useState<Me | null>(null)
  const [clinicId, setClinicIdState] = useState<string | null>(readStoredClinicId)

  const membership = useMemo(() => {
    const selected = me
      ? (me.memberships.find((m) => m.clinic_id === clinicId) ?? me.memberships[0] ?? null)
      : null
    // Set the API client's X-Clinic-Id right away (not in an effect): child pages' queries can
    // start before this component's effects run.
    setClinicId(selected?.clinic_id ?? null)
    return selected
  }, [me, clinicId])

  const reloadMe = useCallback(async () => {
    try {
      const data = await api.get<Me>('/auth/me')
      setMe(data)
      setStatus('authenticated')
      return data
    } catch {
      setMe(null)
      setStatus('anonymous')
      return null
    }
  }, [])

  // On first load: if the browser still has a valid refresh cookie, log straight in.
  useEffect(() => {
    refreshAccessToken().then((ok) => {
      if (ok) void reloadMe()
      else setStatus('anonymous')
    })
  }, [reloadMe])

  const signIn = useCallback(
    async (tokens: TokenResponse) => {
      setAccessToken(tokens.access_token)
      queryClient.clear()
      await reloadMe()
    },
    [queryClient, reloadMe],
  )

  const signOut = useCallback(
    async (everywhere = false) => {
      try {
        await api.post(everywhere ? '/auth/logout-all' : '/auth/logout')
      } finally {
        setAccessToken(null)
        setMe(null)
        setStatus('anonymous')
        queryClient.clear()
      }
    },
    [queryClient],
  )

  const switchClinic = useCallback(
    (id: string) => {
      setClinicIdState(id)
      storeClinicId(id)
      setClinicId(id)
      queryClient.clear() // all cached data belonged to the previous clinic
    },
    [queryClient],
  )

  const value = useMemo(
    () => ({ status, me, membership, signIn, signOut, switchClinic, reloadMe }),
    [status, me, membership, signIn, signOut, switchClinic, reloadMe],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
