import { useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, Outlet } from 'react-router'

import { patientApi } from '@/lib/api'
import type { PatientMe, TokenResponse } from '@/lib/types'

type Status = 'loading' | 'authenticated' | 'anonymous'

type PatientAuth = {
  status: Status
  me: PatientMe | null
  signIn: (tokens: TokenResponse) => Promise<void>
  signOut: () => Promise<void>
  reloadMe: () => Promise<PatientMe | null>
}

const PatientAuthContext = createContext<PatientAuth | null>(null)

/** Login state for the patient app — completely separate from clinic staff login. */
export function PatientAuthProvider() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>('loading')
  const [me, setMe] = useState<PatientMe | null>(null)

  const reloadMe = useCallback(async () => {
    try {
      const data = await patientApi.get<PatientMe>('/patient/me')
      setMe(data)
      setStatus('authenticated')
      return data
    } catch {
      setMe(null)
      setStatus('anonymous')
      return null
    }
  }, [])

  useEffect(() => {
    patientApi.refreshAccessToken().then((ok) => {
      if (ok) void reloadMe()
      else setStatus('anonymous')
    })
  }, [reloadMe])

  const signIn = useCallback(
    async (tokens: TokenResponse) => {
      patientApi.setAccessToken(tokens.access_token)
      await reloadMe()
    },
    [reloadMe],
  )

  const signOut = useCallback(async () => {
    try {
      await patientApi.post('/patient/auth/logout')
    } finally {
      patientApi.setAccessToken(null)
      setMe(null)
      setStatus('anonymous')
      queryClient.removeQueries({ queryKey: ['patient-app'] })
    }
  }, [queryClient])

  const value = useMemo(
    () => ({ status, me, signIn, signOut, reloadMe }),
    [status, me, signIn, signOut, reloadMe],
  )
  return (
    <PatientAuthContext.Provider value={value}>
      <Outlet />
    </PatientAuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePatientAuth(): PatientAuth {
  const context = useContext(PatientAuthContext)
  if (!context) throw new Error('usePatientAuth must be used inside <PatientAuthProvider>')
  return context
}

function Spinner() {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  )
}

/** Patient pages that need a logged-in patient. */
export function RequirePatient() {
  const { status } = usePatientAuth()
  if (status === 'loading') return <Spinner />
  if (status === 'anonymous') return <Navigate to="/patient/login" replace />
  return <Outlet />
}

/** The patient login page: logged-in patients go straight to their profiles. */
export function PatientGuestOnly() {
  const { status } = usePatientAuth()
  if (status === 'loading') return <Spinner />
  if (status === 'authenticated') return <Navigate to="/patient" replace />
  return <Outlet />
}
