import { CalendarDays, FileText, UsersRound } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/features/auth/auth-context'

type Feature = { icon: React.ElementType; title: string; text: string; to?: string }

const FEATURES: Feature[] = [
  {
    icon: UsersRound,
    title: 'Patients',
    text: 'Register patients and find them instantly by name or phone.',
    to: '/patients',
  },
  {
    icon: CalendarDays,
    title: 'Appointments',
    text: 'Book time slots, add walk-ins and run the day’s token queue.',
    to: '/appointments',
  },
  {
    icon: FileText,
    title: 'Prescriptions & reports',
    text: 'Write prescriptions, upload reports, share them on WhatsApp.',
  },
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
        {FEATURES.map(({ icon: Icon, title, text, to }) => {
          const card = (
            <Card className={to ? 'h-full transition-colors hover:border-primary/50' : 'h-full'}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Icon className="size-5 text-muted-foreground" />
                  {to ? <Badge>Open</Badge> : <Badge variant="secondary">Coming soon</Badge>}
                </div>
                <CardTitle className="pt-2">{title}</CardTitle>
                <CardDescription>{text}</CardDescription>
              </CardHeader>
            </Card>
          )
          return to ? (
            <Link key={title} to={to}>
              {card}
            </Link>
          ) : (
            <div key={title}>{card}</div>
          )
        })}
      </div>
    </div>
  )
}
