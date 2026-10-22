import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { CalendarPlus, ChevronLeft, ChevronRight, Footprints } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { SegmentedToggle } from '@/components/SegmentedToggle'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api'
import { addDays, formatDay, formatTime, startOfWeek, todayInZone } from '@/lib/time'
import type { Appointment } from '@/lib/types'
import { cn } from '@/lib/utils'

import { AppointmentItem } from './AppointmentItem'
import { BookDialog } from './BookDialog'
import { useClinicZone, useDoctors } from './hooks'

type View = 'day' | 'week'
type DialogState = { mode: 'book' | 'walk_in' } | { mode: 'reschedule'; appointment: Appointment } | null

const ALL = 'all'
const VIEW_OPTIONS = [
  { value: 'day' as const, label: 'Day' },
  { value: 'week' as const, label: 'Week' },
]

export function AppointmentsPage() {
  const zone = useClinicZone()
  const doctors = useDoctors()
  const [today] = useState(() => todayInZone(zone))
  const [day, setDay] = useState(today)
  const [view, setView] = useState<View>('day')
  const [doctorId, setDoctorId] = useState(ALL)
  const [dialog, setDialog] = useState<DialogState>(null)

  const first = view === 'day' ? day : startOfWeek(day)
  const last = view === 'day' ? day : addDays(first, 6)
  const doctorParam = doctorId === ALL ? '' : `&doctor_id=${doctorId}`
  const appointments = useQuery({
    queryKey: ['appointments', first, last, doctorId],
    queryFn: () =>
      api.get<Appointment[]>(`/appointments?start_date=${first}&end_date=${last}${doctorParam}`),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000, // keep the front desk's view fresh
  })
  const list = appointments.data ?? []
  const step = view === 'day' ? 1 : 7
  const multipleDoctors = (doctors.data?.length ?? 0) > 1

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Appointments</h1>
          <p className="text-muted-foreground">
            {view === 'day'
              ? `${formatDay(day, { weekday: 'long', month: 'long' })}${day === today ? ' · Today' : ''}`
              : `${formatDay(first)} – ${formatDay(last)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setDialog({ mode: 'walk_in' })}>
            <Footprints /> Add walk-in
          </Button>
          <Button onClick={() => setDialog({ mode: 'book' })}>
            <CalendarPlus /> Book appointment
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" aria-label="Previous" onClick={() => setDay(addDays(day, -step))}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" onClick={() => setDay(today)} disabled={day === today}>
            Today
          </Button>
          <Button variant="outline" size="icon" aria-label="Next" onClick={() => setDay(addDays(day, step))}>
            <ChevronRight />
          </Button>
        </div>
        <Input
          type="date"
          aria-label="Go to date"
          className="w-40"
          value={day}
          onChange={(e) => e.target.value && setDay(e.target.value)}
        />
        <div className="w-40">
          <SegmentedToggle label="View" options={VIEW_OPTIONS} value={view} onChange={setView} />
        </div>
        {multipleDoctors && (
          <Select value={doctorId} onValueChange={setDoctorId}>
            <SelectTrigger className="w-56" aria-label="Doctor">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All doctors</SelectItem>
              {doctors.data?.map((d) => (
                <SelectItem key={d.user_id} value={d.user_id}>
                  {d.full_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {doctors.data?.length === 0 && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">
            No doctors to book yet. Invite a doctor from <Link to="/team" className="underline">Team</Link>,
            then set their working hours in{' '}
            <Link to="/doctor-hours" className="underline">Doctor hours</Link>.
          </CardContent>
        </Card>
      )}
      {doctors.data?.length !== 0 && doctors.data?.every((d) => d.sessions.length === 0) && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">
            Set your doctors&apos; working hours in{' '}
            <Link to="/doctor-hours" className="underline">Doctor hours</Link> to start booking
            time slots. Walk-ins work without them.
          </CardContent>
        </Card>
      )}

      {view === 'day' ? (
        <DayView
          appointments={list}
          zone={zone}
          isToday={day === today}
          showDoctor={multipleDoctors && doctorId === ALL}
          loading={appointments.isPending}
          onReschedule={(appointment) => setDialog({ mode: 'reschedule', appointment })}
        />
      ) : (
        <WeekView
          appointments={list}
          zone={zone}
          first={first}
          today={today}
          onPickDay={(d) => {
            setDay(d)
            setView('day')
          }}
        />
      )}

      {dialog && (
        <BookDialog
          mode={dialog.mode}
          appointment={dialog.mode === 'reschedule' ? dialog.appointment : undefined}
          initialDay={day < today ? today : day}
          initialDoctorId={doctorId === ALL ? undefined : doctorId}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  )
}

function DayView({
  appointments,
  zone,
  isToday,
  showDoctor,
  loading,
  onReschedule,
}: {
  appointments: Appointment[]
  zone: string
  isToday: boolean
  showDoctor: boolean
  loading: boolean
  onReschedule: (appointment: Appointment) => void
}) {
  const queue = appointments
    .filter((a) => a.status === 'arrived' || a.status === 'in_consultation')
    .sort((a, b) => (a.token_number ?? 0) - (b.token_number ?? 0))
  const withDoctor = queue.filter((a) => a.status === 'in_consultation')
  const waiting = queue.filter((a) => a.status === 'arrived')

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
      <div className="flex flex-col gap-2">
        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!loading && appointments.length === 0 && (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No appointments this day.
            </CardContent>
          </Card>
        )}
        {appointments.map((a) => (
          <AppointmentItem
            key={a.id}
            appointment={a}
            zone={zone}
            isToday={isToday}
            showDoctor={showDoctor}
            onReschedule={onReschedule}
          />
        ))}
      </div>

      {isToday && (
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              Queue
              <Badge variant="secondary">{waiting.length} waiting</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            <QueueGroup title="With doctor" items={withDoctor} showDoctor={showDoctor} />
            <QueueGroup title="Waiting" items={waiting} showDoctor={showDoctor} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function QueueGroup({
  title,
  items,
  showDoctor,
}: {
  title: string
  items: Appointment[]
  showDoctor: boolean
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</div>
      {items.length === 0 && <div className="text-muted-foreground">—</div>}
      {items.map((a) => (
        <div key={a.id} className="flex items-center gap-2">
          <span className="w-8 font-semibold tabular-nums">#{a.token_number}</span>
          <span className="flex-1 truncate">
            {a.patient_name}
            {showDoctor && <span className="block truncate text-xs text-muted-foreground">{a.doctor_name}</span>}
          </span>
        </div>
      ))}
    </div>
  )
}

function WeekView({
  appointments,
  zone,
  first,
  today,
  onPickDay,
}: {
  appointments: Appointment[]
  zone: string
  first: string
  today: string
  onPickDay: (day: string) => void
}) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(first, i))
  return (
    <div className="grid gap-2 sm:grid-cols-7">
      {days.map((d) => {
        const items = appointments.filter((a) => a.visit_date === d && a.status !== 'cancelled')
        return (
          <Card key={d} className={cn('gap-2 py-3', d === today && 'border-primary')}>
            <button
              type="button"
              onClick={() => onPickDay(d)}
              className="px-3 text-left text-sm font-medium hover:underline"
            >
              {formatDay(d)}
              <span className="block text-xs font-normal text-muted-foreground">
                {items.length} appointment{items.length === 1 ? '' : 's'}
              </span>
            </button>
            <div className="flex flex-col gap-1 px-2">
              {items.slice(0, 8).map((a) => (
                <div key={a.id} className="truncate rounded bg-muted px-1.5 py-1 text-xs">
                  <span className="tabular-nums">
                    {a.kind === 'walk_in' ? `#${a.token_number}` : formatTime(a.start_at, zone)}
                  </span>{' '}
                  {a.patient_name}
                </div>
              ))}
              {items.length > 8 && (
                <button type="button" onClick={() => onPickDay(d)} className="text-xs text-muted-foreground hover:underline">
                  +{items.length - 8} more
                </button>
              )}
            </div>
          </Card>
        )
      })}
    </div>
  )
}
