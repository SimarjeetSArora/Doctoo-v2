import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FormError } from '@/features/auth/FormError'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { formatDay, formatTime, todayInZone } from '@/lib/time'
import type { Appointment } from '@/lib/types'

import { useClinicZone, useDoctors } from './hooks'
import { type PickedPatient, PatientPicker } from './PatientPicker'
import { SlotPicker } from './SlotPicker'

type Mode = 'book' | 'walk_in' | 'reschedule'

/**
 * Book a time slot, add a walk-in to today's queue, or reschedule an existing booking.
 * Render it only while open (it starts fresh each time).
 */
export function BookDialog({
  mode,
  onClose,
  patient: initialPatient = null,
  appointment,
  initialDay,
  initialDoctorId,
}: {
  mode: Mode
  onClose: () => void
  patient?: PickedPatient | null
  appointment?: Appointment
  initialDay?: string
  initialDoctorId?: string
}) {
  const queryClient = useQueryClient()
  const zone = useClinicZone()
  const doctors = useDoctors()
  const [today] = useState(() => todayInZone(zone))
  const [patient, setPatient] = useState<PickedPatient | null>(
    appointment
      ? { id: appointment.patient_id, full_name: appointment.patient_name, phone: appointment.patient_phone }
      : initialPatient,
  )
  const [doctorId, setDoctorId] = useState(
    appointment?.doctor_id ?? initialDoctorId ?? '',
  )
  const effectiveDoctorId = doctorId || (doctors.data?.length === 1 ? doctors.data[0].user_id : '')
  const [day, setDay] = useState(appointment?.visit_date ?? initialDay ?? today)
  const [startAt, setStartAt] = useState<string | null>(appointment?.start_at ?? null)
  const [reason, setReason] = useState(appointment?.reason ?? '')
  const [error, setError] = useState<string>()
  const [missing, setMissing] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const title = { book: 'Book appointment', walk_in: 'Add walk-in', reschedule: 'Reschedule' }[mode]

  async function save() {
    const problems: Record<string, string> = {}
    if (!patient) problems.patient = 'Choose a patient'
    if (!effectiveDoctorId) problems.doctor = 'Choose a doctor'
    if (mode !== 'walk_in' && !startAt) problems.time = 'Choose a time'
    setMissing(problems)
    if (Object.keys(problems).length) return

    setSaving(true)
    setError(undefined)
    try {
      let saved: Appointment
      if (mode === 'reschedule' && appointment) {
        saved = await api.patch<Appointment>(`/appointments/${appointment.id}`, {
          doctor_id: effectiveDoctorId,
          start_at: startAt,
          reason: reason || null,
        })
        toast.success(`Moved to ${formatDay(saved.visit_date)}, ${formatTime(saved.start_at, zone)}`)
      } else {
        saved = await api.post<Appointment>('/appointments', {
          patient_id: patient!.id,
          doctor_id: effectiveDoctorId,
          kind: mode === 'walk_in' ? 'walk_in' : 'scheduled',
          start_at: mode === 'walk_in' ? null : startAt,
          reason: reason || null,
        })
        toast.success(
          mode === 'walk_in'
            ? `${saved.patient_name} added to the queue — token #${saved.token_number}`
            : `Booked ${saved.patient_name} for ${formatDay(saved.visit_date)}, ${formatTime(saved.start_at, zone)}`,
        )
      }
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['slots'] })
      onClose()
    } catch (e) {
      setError(errorText(e))
      queryClient.invalidateQueries({ queryKey: ['slots'] }) // the slot may have just been taken
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {mode === 'walk_in'
              ? 'They join today’s queue now and get the next token number.'
              : mode === 'reschedule'
                ? 'Pick a new day and time.'
                : 'Choose the patient, doctor and a free time.'}
          </DialogDescription>
        </DialogHeader>
        <FieldGroup className="py-2">
          <FormError message={error} />
          <Field data-invalid={!!missing.patient}>
            <FieldLabel htmlFor="patient">Patient</FieldLabel>
            {mode === 'reschedule' ? (
              <div className="text-sm font-medium">{patient?.full_name}</div>
            ) : (
              <PatientPicker value={patient} onChange={setPatient} invalid={!!missing.patient} />
            )}
            <FieldError>{missing.patient}</FieldError>
          </Field>

          <Field data-invalid={!!missing.doctor}>
            <FieldLabel htmlFor="doctor">Doctor</FieldLabel>
            <Select
              value={effectiveDoctorId}
              onValueChange={(id) => {
                setDoctorId(id)
                setStartAt(null)
              }}
            >
              <SelectTrigger id="doctor" className="w-full" aria-invalid={!!missing.doctor}>
                <SelectValue placeholder="Choose a doctor" />
              </SelectTrigger>
              <SelectContent>
                {doctors.data?.map((d) => (
                  <SelectItem key={d.user_id} value={d.user_id}>
                    {d.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {doctors.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No doctors yet. Invite a doctor, or register yourself with the title Dr.
              </p>
            )}
            <FieldError>{missing.doctor}</FieldError>
          </Field>

          {mode !== 'walk_in' && (
            <>
              <Field>
                <FieldLabel htmlFor="day">Date</FieldLabel>
                <Input
                  id="day"
                  type="date"
                  min={today}
                  value={day}
                  onChange={(e) => {
                    setDay(e.target.value)
                    setStartAt(null)
                  }}
                />
              </Field>
              <Field data-invalid={!!missing.time}>
                <FieldLabel>Time</FieldLabel>
                {effectiveDoctorId && day ? (
                  <SlotPicker
                    doctorId={effectiveDoctorId}
                    day={day}
                    zone={zone}
                    value={startAt}
                    onChange={setStartAt}
                    keep={appointment?.start_at}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">Choose a doctor to see free times.</p>
                )}
                <FieldError>{missing.time}</FieldError>
              </Field>
            </>
          )}

          <Field>
            <FieldLabel htmlFor="reason">Reason (optional)</FieldLabel>
            <Input
              id="reason"
              placeholder="Fever, follow-up, vaccination…"
              maxLength={300}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : mode === 'walk_in' ? 'Add to queue' : mode === 'reschedule' ? 'Move appointment' : 'Book'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
