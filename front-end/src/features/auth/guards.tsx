import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuth } from './auth-context'

export function FullPageSpinner() {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  )
}

/** Logged-in users only. Users without any clinic are sent to create one. */
export function RequireAuth() {
  const { status, membership } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <FullPageSpinner />
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (!membership && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />
  }
  return <Outlet />
}

/** Login / sign-up pages: logged-in users go straight to the app. */
export function GuestOnly() {
  const { status } = useAuth()
  if (status === 'loading') return <FullPageSpinner />
  if (status === 'authenticated') return <Navigate to="/" replace />
  return <Outlet />
}
