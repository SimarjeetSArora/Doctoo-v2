import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { formatTime } from '@/lib/time'
import type { Slot } from '@/lib/types'
import { cn } from '@/lib/utils'

/** The doctor's slots for a day; taken or past ones are disabled. */
export function SlotPicker({
  doctorId,
  day,
  zone,
  value,
  onChange,
  keep,
}: {
  doctorId: string
  day: string
  zone: string
  value: string | null
  onChange: (startAt: string) => void
  /** When rescheduling, the appointment's current slot counts as free. */
  keep?: string
}) {
  const slots = useQuery({
    queryKey: ['slots', doctorId, day],
    queryFn: () => api.get<Slot[]>(`/appointments/slots?doctor_id=${doctorId}&date=${day}`),
    enabled: !!doctorId && !!day,
  })

  if (slots.isPending) return <p className="text-sm text-muted-foreground">Loading times…</p>
  if (!slots.data?.length) {
    return (
      <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        The doctor isn&apos;t working this day. Pick another date, or set their hours in Doctor
        hours.
      </p>
    )
  }
  const free = slots.data.filter((s) => s.available || s.start_at === keep).length

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-5" role="listbox" aria-label="Available times">
        {slots.data.map((slot) => {
          const available = slot.available || slot.start_at === keep
          const selected = value !== null && new Date(value).getTime() === new Date(slot.start_at).getTime()
          return (
            <button
              key={slot.start_at}
              type="button"
              role="option"
              aria-selected={selected}
              disabled={!available}
              onClick={() => onChange(slot.start_at)}
              className={cn(
                'rounded-md border px-2 py-1.5 text-sm tabular-nums transition-colors',
                available ? 'hover:border-primary' : 'cursor-not-allowed bg-muted text-muted-foreground line-through',
                selected &&
                  'border-primary bg-primary font-semibold text-primary-foreground ring-2 ring-primary/30 ring-offset-1 hover:border-primary hover:bg-primary',
              )}
            >
              {formatTime(slot.start_at, zone)}
            </button>
          )
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        {free} of {slots.data.length} times free
      </p>
    </div>
  )
}
