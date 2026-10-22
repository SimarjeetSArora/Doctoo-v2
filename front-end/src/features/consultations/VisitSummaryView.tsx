import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useClinicZone } from '@/features/appointments/hooks'
import { dateInZone, formatDay, formatTime } from '@/lib/time'
import type { Visit, Vitals } from '@/lib/types'

const VITALS: { key: keyof Vitals; label: string; unit: string }[] = [
  { key: 'pulse', label: 'Pulse', unit: '/min' },
  { key: 'temperature_f', label: 'Temp', unit: '°F' },
  { key: 'spo2', label: 'SpO₂', unit: '%' },
  { key: 'respiratory_rate', label: 'Resp. rate', unit: '/min' },
  { key: 'blood_sugar', label: 'Sugar', unit: 'mg/dL' },
  { key: 'weight_kg', label: 'Weight', unit: 'kg' },
  { key: 'height_cm', label: 'Height', unit: 'cm' },
]

function Section({ title, text }: { title: string; text: string | null }) {
  if (!text) return null
  return (
    <div className="flex flex-col gap-1">
      <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</div>
      <p className="whitespace-pre-line">{text}</p>
    </div>
  )
}

/** Read-only view of a consultation (finished, or someone else's in progress). */
export function VisitSummaryView({ visit }: { visit: Visit }) {
  const zone = useClinicZone()
  const when = visit.completed_at ?? visit.created_at
  const v = visit.vitals
  const vitals = [
    v.bp_systolic && v.bp_diastolic ? `BP ${v.bp_systolic}/${v.bp_diastolic} mmHg` : null,
    ...VITALS.filter((f) => v[f.key] != null).map((f) => `${f.label} ${v[f.key]}${f.unit}`),
  ].filter(Boolean)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{visit.prescription_number ?? 'Consultation in progress'}</CardTitle>
        <CardDescription>
          {formatDay(dateInZone(when, zone), { weekday: 'long', year: 'numeric' })} at{' '}
          {formatTime(when, zone)} · {visit.doctor_name}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 text-sm">
        {vitals.length > 0 && <div className="text-muted-foreground">{vitals.join('  ·  ')}</div>}
        <Section title="Complaints" text={visit.complaints} />
        <Section title="Examination" text={visit.examination} />
        <Section title="Diagnosis" text={visit.diagnosis} />
        {visit.items.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              ℞ Prescription
            </div>
            <ol className="flex flex-col divide-y rounded-lg border">
              {visit.items.map((item, i) => (
                <li key={i} className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2">
                  <span className="w-5 text-muted-foreground">{i + 1}.</span>
                  <span className="min-w-40 flex-1 font-medium">{item.medicine}</span>
                  <span className="tabular-nums">{item.dose}</span>
                  {item.timing && <span>{item.timing}</span>}
                  {item.duration && <span>{item.duration}</span>}
                  {item.instructions && (
                    <span className="w-full pl-9 text-muted-foreground">{item.instructions}</span>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}
        <Section title="Advice" text={visit.advice} />
        {visit.follow_up_date && (
          <div className="font-medium">
            Follow-up on {formatDay(visit.follow_up_date, { weekday: 'long', year: 'numeric' })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
