import { HeartPulse, LogOut } from 'lucide-react'
import { Link, Outlet } from 'react-router'

import { Button } from '@/components/ui/button'
import { formatPhone } from '@/lib/phone'

import { usePatientAuth } from './patient-auth'

/** Mobile-first shell for the patient app. */
export function PatientLayout() {
  const { me, signOut } = usePatientAuth()
  return (
    <div className="min-h-svh bg-muted/40">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4">
          <Link to="/patient" className="flex items-center gap-2 font-semibold">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <HeartPulse className="size-4" />
            </span>
            Doctoo
          </Link>
          <div className="flex items-center gap-2">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {formatPhone(me?.phone)}
            </span>
            <Button variant="ghost" size="sm" onClick={() => signOut()}>
              <LogOut /> Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-2xl p-4 pb-12">
        <Outlet />
      </main>
    </div>
  )
}
