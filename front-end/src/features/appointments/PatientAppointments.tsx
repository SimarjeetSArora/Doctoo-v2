import { useQuery } from '@tanstack/react-query'
import { CalendarPlus } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { formatDay, formatTime, todayInZone } from '@/lib/time'
import type { Appointment, Patient } from '@/lib/types'

import { BookDialog } from './BookDialog'
import { useClinicZone } from './hooks'
import { StatusBadge } from './StatusBadge'

/** A patient's appointment history on their page, with a "Book" button. */
export function PatientAppointments({ patient }: { patient: Patient }) {
  const zone = useClinicZone()
  const [booking, setBooking] = useState(false)
  const [today] = useState(() => todayInZone(zone))
  const appointments = useQuery({
    queryKey: ['appointments', 'patient', patient.id],
    queryFn: () => api.get<Appointment[]>(`/appointments?patient_id=${patient.id}`),
  })
  const list = appointments.data ?? []
  const upcoming = list.filter((a) => a.visit_date >= today && a.status === 'booked').reverse()
  const past = list.filter((a) => !upcoming.includes(a))

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <CardTitle>Appointments</CardTitle>
          <CardDescription>
            {list.length === 0 ? 'No appointments yet.' : `${upcoming.length} upcoming · ${past.length} past`}
          </CardDescription>
        </div>
        <Button onClick={() => setBooking(true)}>
          <CalendarPlus /> Book
        </Button>
      </CardHeader>
      {list.length > 0 && (
        <CardContent className="flex flex-col divide-y">
          {[...upcoming, ...past].slice(0, 10).map((a) => (
            <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
              <div>
                <div className="font-medium">
                  {formatDay(a.visit_date)} ·{' '}
                  {a.kind === 'walk_in' ? `Walk-in #${a.token_number}` : formatTime(a.start_at, zone)}
                </div>
                <div className="text-muted-foreground">
                  {[a.doctor_name, a.reason].filter(Boolean).join(' · ')}
                </div>
              </div>
              <StatusBadge status={a.status} />
            </div>
          ))}
        </CardContent>
      )}
      {booking && (
        <BookDialog
          mode="book"
          patient={{ id: patient.id, full_name: patient.full_name, phone: patient.phone }}
          onClose={() => setBooking(false)}
        />
      )}
    </Card>
  )
}
