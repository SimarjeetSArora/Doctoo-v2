import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, ArrowLeft, FlaskConical, Pencil, Phone } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
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
import { PatientAppointments } from '@/features/appointments/PatientAppointments'
import { useAuth } from '@/features/auth/auth-context'
import { PatientVisits } from '@/features/consultations/PatientVisits'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { ageAndGender, formatDate, initials } from '@/lib/format'
import { formatPhone } from '@/lib/phone'
import type { Patient } from '@/lib/types'

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value || '—'}</dd>
    </div>
  )
}

const COMING_NEXT = [
  { icon: FlaskConical, title: 'Reports', text: 'Lab reports and scans.' },
]

export function PatientDetailPage() {
  const { patientId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { membership } = useAuth()
  const canArchive = membership?.role === 'owner' || membership?.role === 'doctor'
  const [confirmArchive, setConfirmArchive] = useState(false)
  const [archiving, setArchiving] = useState(false)

  const patient = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => api.get<Patient>(`/patients/${patientId}`),
  })

  async function archive() {
    setArchiving(true)
    try {
      await api.delete(`/patients/${patientId}`)
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast.success('Patient archived')
      navigate('/patients', { replace: true })
    } catch (e) {
      toast.error(errorText(e))
      setArchiving(false)
    }
  }

  if (patient.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (!patient.data) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-muted-foreground">
          Patient not found. <Link to="/patients" className="underline">Back to patients</Link>
        </p>
      </div>
    )
  }
  const p = patient.data

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <Link to="/patients" className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Patients
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Avatar className="size-14">
            <AvatarFallback className="text-lg">{initials(p.full_name)}</AvatarFallback>
          </Avatar>
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">{p.full_name}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {ageAndGender(p.age, p.gender) && <span>{ageAndGender(p.age, p.gender)}</span>}
              <a href={`tel:${p.phone}`} className="flex items-center gap-1 hover:text-foreground">
                <Phone className="size-3.5" />
                {formatPhone(p.phone)}
              </a>
              {p.blood_group && <Badge variant="outline">{p.blood_group}</Badge>}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to={`/patients/${p.id}/edit`}>
              <Pencil /> Edit
            </Link>
          </Button>
          {canArchive && (
            <Button variant="outline" onClick={() => setConfirmArchive(true)}>
              <Archive /> Archive
            </Button>
          )}
        </div>
      </div>

      {p.notes && (
        <Card className="border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40">
          <CardHeader>
            <CardTitle className="text-sm">Medical notes</CardTitle>
            <CardDescription className="whitespace-pre-line text-foreground">{p.notes}</CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-3">
            <Detail label="Date of birth" value={formatDate(p.date_of_birth)} />
            <Detail label="Email" value={p.email} />
            <Detail label="ABHA number" value={p.abha_number} />
            <Detail label="Address" value={p.address} />
            <Detail
              label="WhatsApp / SMS consent"
              value={
                p.messaging_consent ? `Yes, since ${formatDate(p.messaging_consent_at)}` : 'Not given'
              }
            />
            <Detail label="Registered" value={formatDate(p.created_at)} />
          </dl>
        </CardContent>
      </Card>

      <PatientAppointments patient={p} />

      <PatientVisits patientId={p.id} />

      <div className="grid gap-4 md:grid-cols-2">
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

      <Dialog open={confirmArchive} onOpenChange={setConfirmArchive}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Archive {p.full_name}?</DialogTitle>
            <DialogDescription>
              They&apos;ll be hidden from the patient list and the patient app. Their records are
              kept, as medical records must be.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmArchive(false)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={archiving} onClick={archive}>
              {archiving ? 'Archiving…' : 'Archive patient'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
