import { useQueryClient } from '@tanstack/react-query'
import { Clock, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/features/auth/auth-context'
import { FormError } from '@/features/auth/FormError'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { formatClock, WEEKDAYS } from '@/lib/time'
import type { Doctor, DoctorSession } from '@/lib/types'

import { useDoctors } from './hooks'

const SLOT_CHOICES = [5, 10, 15, 20, 30, 45, 60]

// Common Indian OPD timings: Monday–Saturday, morning and evening.
const PRESET: DoctorSession[] = [0, 1, 2, 3, 4, 5].flatMap((weekday) => [
  { weekday, start_time: '10:00', end_time: '13:00', slot_minutes: 15 },
  { weekday, start_time: '17:00', end_time: '20:00', slot_minutes: 15 },
])

export function DoctorHoursPage() {
  const { me, membership } = useAuth()
  const doctors = useDoctors()
  const [editing, setEditing] = useState<Doctor | null>(null)
  const canEdit = (d: Doctor) => membership?.role === 'owner' || d.user_id === me?.user.id

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Doctor hours</h1>
        <p className="text-muted-foreground">
          Weekly working hours decide which appointment slots can be booked.
        </p>
      </div>

      {doctors.data?.length === 0 && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">
            No doctors yet. Invite doctors from Team. Clinic owners registered with the title “Dr.”
            are listed here too.
          </CardContent>
        </Card>
      )}

      {doctors.data?.map((doctor) => (
        <Card key={doctor.user_id}>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div className="flex flex-col gap-1.5">
              <CardTitle>{doctor.full_name}</CardTitle>
              <CardDescription>
                {doctor.sessions.length === 0
                  ? 'No working hours yet — this doctor can’t be booked.'
                  : `${new Set(doctor.sessions.map((s) => s.weekday)).size} days a week`}
              </CardDescription>
            </div>
            {canEdit(doctor) && (
              <Button variant="outline" onClick={() => setEditing(doctor)}>
                <Clock /> Edit hours
              </Button>
            )}
          </CardHeader>
          {doctor.sessions.length > 0 && (
            <CardContent>
              <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                {WEEKDAYS.map((name, weekday) => {
                  const sessions = doctor.sessions.filter((s) => s.weekday === weekday)
                  return (
                    <div key={name} className="flex justify-between gap-4 border-b py-1.5 last:border-0">
                      <dt className="text-muted-foreground">{name}</dt>
                      <dd className="text-right">
                        {sessions.length === 0
                          ? 'Off'
                          : sessions
                              .map((s) => `${formatClock(s.start_time)}–${formatClock(s.end_time)}`)
                              .join(', ')}
                      </dd>
                    </div>
                  )
                })}
              </dl>
            </CardContent>
          )}
        </Card>
      ))}

      {editing && <HoursDialog doctor={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

type Row = DoctorSession & { key: number }
let nextKey = 1

function toRows(sessions: DoctorSession[]): Row[] {
  return sessions.map((s) => ({
    ...s,
    start_time: s.start_time.slice(0, 5),
    end_time: s.end_time.slice(0, 5),
    key: nextKey++,
  }))
}

function HoursDialog({ doctor, onClose }: { doctor: Doctor; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<Row[]>(() => toRows(doctor.sessions))
  const [error, setError] = useState<string>()
  const [saving, setSaving] = useState(false)

  function update(key: number, change: Partial<DoctorSession>) {
    setRows((current) => current.map((r) => (r.key === key ? { ...r, ...change } : r)))
  }

  async function save() {
    setSaving(true)
    setError(undefined)
    try {
      await api.put<Doctor>(`/doctors/${doctor.user_id}/schedule`, {
        sessions: rows.map(({ key: _key, ...session }) => session),
      })
      queryClient.invalidateQueries({ queryKey: ['doctors'] })
      queryClient.invalidateQueries({ queryKey: ['slots'] })
      toast.success(`Hours saved for ${doctor.full_name}`)
      onClose()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Working hours — {doctor.full_name}</DialogTitle>
          <DialogDescription>
            Add one or more sessions per day (e.g. morning and evening OPD). Existing bookings are
            not changed.
          </DialogDescription>
        </DialogHeader>
        <FormError message={error} />
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setRows(toRows(PRESET))}>
            Use Mon–Sat 10–1 & 5–8
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => setRows([])}>
            Clear all
          </Button>
        </div>
        <div className="flex flex-col divide-y">
          {WEEKDAYS.map((name, weekday) => {
            const dayRows = rows.filter((r) => r.weekday === weekday)
            return (
              <div key={name} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start">
                <div className="w-28 shrink-0 pt-2 text-sm font-medium">{name}</div>
                <div className="flex flex-1 flex-col gap-2">
                  {dayRows.length === 0 && <div className="pt-2 text-sm text-muted-foreground">Off</div>}
                  {dayRows.map((row) => (
                    <div key={row.key} className="flex flex-wrap items-center gap-2">
                      <Input
                        type="time"
                        aria-label={`${name} start`}
                        className="w-32"
                        value={row.start_time}
                        onChange={(e) => update(row.key, { start_time: e.target.value })}
                      />
                      <span className="text-muted-foreground">to</span>
                      <Input
                        type="time"
                        aria-label={`${name} end`}
                        className="w-32"
                        value={row.end_time}
                        onChange={(e) => update(row.key, { end_time: e.target.value })}
                      />
                      <Select
                        value={String(row.slot_minutes)}
                        onValueChange={(v) => update(row.key, { slot_minutes: Number(v) })}
                      >
                        <SelectTrigger className="w-32" aria-label={`${name} slot length`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SLOT_CHOICES.map((m) => (
                            <SelectItem key={m} value={String(m)}>
                              {m} min slots
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove ${name} session`}
                        onClick={() => setRows((current) => current.filter((r) => r.key !== row.key))}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="w-fit"
                    onClick={() =>
                      setRows((current) => [
                        ...current,
                        { weekday, start_time: '10:00', end_time: '13:00', slot_minutes: 15, key: nextKey++ },
                      ])
                    }
                  >
                    <Plus /> Add session
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save hours'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
