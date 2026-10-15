import { CalendarDays, Receipt, UsersRound } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/features/auth/auth-context'

const COMING_NEXT = [
  { icon: UsersRound, title: 'Patients', text: 'Register patients and find them instantly by phone.' },
  { icon: CalendarDays, title: 'Appointments', text: 'Day and week calendar for every doctor.' },
  { icon: Receipt, title: 'Billing', text: 'GST-ready invoices, UPI payments and daily collections.' },
]

export function DashboardPage() {
  const { me, membership } = useAuth()
  const user = me?.user
  // "Dr. Simarjeet" for doctors/professors, otherwise just the first name.
  const greetingName =
    user && (user.salutation === 'Dr.' || user.salutation === 'Prof.')
      ? `${user.salutation} ${user.first_name}`
      : user?.first_name

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Hello, {greetingName}</h1>
        <p className="text-muted-foreground">{membership?.clinic_name} is set up on Doctoo.</p>
      </div>

      {membership?.role === 'owner' && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-1.5">
              <CardTitle>Bring your team on board</CardTitle>
              <CardDescription>
                Invite your doctors and receptionists so everyone works from the same system.
              </CardDescription>
            </div>
            <Button asChild>
              <Link to="/team">Invite team</Link>
            </Button>
          </CardHeader>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {COMING_NEXT.map(({ icon: Icon, title, text }) => (
          <Card key={title}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <Icon className="size-5 text-muted-foreground" />
                <Badge variant="secondary">Coming soon</Badge>
              </div>
              <CardTitle className="pt-2">{title}</CardTitle>
              <CardDescription>{text}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  )
}
