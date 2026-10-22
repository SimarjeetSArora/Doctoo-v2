import { useQuery } from '@tanstack/react-query'
import { ChevronRight, FileText } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useClinicZone } from '@/features/appointments/hooks'
import { api } from '@/lib/api'
import { dateInZone, formatDay } from '@/lib/time'
import type { VisitSummary } from '@/lib/types'

/** A patient's consultations and prescriptions, newest first. */
export function PatientVisits({ patientId }: { patientId: string }) {
  const zone = useClinicZone()
  const visits = useQuery({
    queryKey: ['visits', patientId],
    queryFn: () => api.get<VisitSummary[]>(`/visits?patient_id=${patientId}`),
  })
  const list = visits.data ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle>Consultations & prescriptions</CardTitle>
        <CardDescription>
          {list.length === 0
            ? 'None yet. Start a consultation from Appointments once the patient is checked in.'
            : `${list.length} consultation${list.length === 1 ? '' : 's'}`}
        </CardDescription>
      </CardHeader>
      {list.length > 0 && (
        <CardContent className="flex flex-col divide-y">
          {list.map((v) => (
            <Link
              key={v.id}
              to={`/consultations/${v.id}`}
              className="flex items-center gap-3 py-2.5 text-sm hover:bg-muted/50"
            >
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="font-medium">
                  {formatDay(dateInZone(v.completed_at ?? v.created_at, zone), { year: 'numeric' })}
                  {v.diagnosis && <span className="font-normal"> · {v.diagnosis}</span>}
                </div>
                <div className="truncate text-muted-foreground">
                  {[v.doctor_name, v.medicines.join(', ')].filter(Boolean).join(' · ')}
                </div>
              </div>
              {v.prescription_number ? (
                <Badge variant="outline">{v.prescription_number}</Badge>
              ) : (
                <Badge variant="secondary">In progress</Badge>
              )}
              <ChevronRight className="size-4 text-muted-foreground" />
            </Link>
          ))}
        </CardContent>
      )}
    </Card>
  )
}
