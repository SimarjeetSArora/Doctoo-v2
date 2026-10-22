import { MoreHorizontal } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatTime } from '@/lib/time'
import type { Appointment, AppointmentStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

import { useChangeStatus, useOpenConsultation } from './hooks'
import { StatusBadge } from './StatusBadge'

// The obvious next step for each status, shown as a button.
// (Starting a consultation opens the consultation screen instead.)
const NEXT_STEP: Partial<Record<AppointmentStatus, { to: AppointmentStatus; label: string }>> = {
  booked: { to: 'arrived', label: 'Check in' },
}

export function AppointmentItem({
  appointment: a,
  zone,
  isToday,
  showDoctor,
  onReschedule,
}: {
  appointment: Appointment
  zone: string
  isToday: boolean
  showDoctor?: boolean
  onReschedule: (appointment: Appointment) => void
}) {
  const changeStatus = useChangeStatus()
  const openConsultation = useOpenConsultation()
  const next = NEXT_STEP[a.status]
  const canCheckIn = a.status !== 'booked' || isToday
  const done = a.status === 'completed' || a.status === 'cancelled' || a.status === 'no_show'

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-3 rounded-lg border bg-card p-3',
        done && 'opacity-70',
      )}
    >
      <div className="w-20 shrink-0 tabular-nums">
        {a.kind === 'walk_in' ? (
          <div className="text-sm font-medium">Walk-in</div>
        ) : (
          <div className="text-sm font-medium">{formatTime(a.start_at, zone)}</div>
        )}
        {a.token_number && (
          <Badge variant="secondary" className="mt-1 tabular-nums">
            #{a.token_number}
          </Badge>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <Link to={`/patients/${a.patient_id}`} className="font-medium hover:underline">
          {a.patient_name}
        </Link>
        <div className="truncate text-sm text-muted-foreground">
          {[showDoctor ? a.doctor_name : null, a.reason].filter(Boolean).join(' · ') || ' '}
        </div>
      </div>
      <StatusBadge status={a.status} />
      {next && canCheckIn && (
        <Button
          size="sm"
          variant={a.status === 'booked' ? 'outline' : 'default'}
          disabled={changeStatus.isPending}
          onClick={() => changeStatus.mutate({ id: a.id, status: next.to })}
        >
          {next.label}
        </Button>
      )}
      {(a.status === 'arrived' || a.status === 'in_consultation') && (
        <Button
          size="sm"
          disabled={openConsultation.isPending}
          onClick={() => openConsultation.mutate(a.id)}
        >
          {a.status === 'arrived' ? 'Start' : 'Open consultation'}
        </Button>
      )}
      {!done && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={`More actions for ${a.patient_name}`}>
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {a.status === 'booked' && a.kind === 'scheduled' && (
              <DropdownMenuItem onSelect={() => onReschedule(a)}>Reschedule</DropdownMenuItem>
            )}
            {(a.status === 'booked' || a.status === 'arrived') && (
              <DropdownMenuItem onSelect={() => changeStatus.mutate({ id: a.id, status: 'no_show' })}>
                Mark no-show
              </DropdownMenuItem>
            )}
            {(a.status === 'booked' || a.status === 'arrived') && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onSelect={() => changeStatus.mutate({ id: a.id, status: 'cancelled' })}
                >
                  Cancel appointment
                </DropdownMenuItem>
              </>
            )}
            {a.status === 'in_consultation' && (
              <DropdownMenuItem onSelect={() => changeStatus.mutate({ id: a.id, status: 'completed' })}>
                Mark completed without notes
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
}
