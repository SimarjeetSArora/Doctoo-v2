import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, CalendarDays, Download, FileText, FlaskConical, Mail, MapPin, Phone, Stethoscope } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { patientApi } from '@/lib/api'
import { saveBlob } from '@/lib/files'
import { ageAndGender, formatDate, initials } from '@/lib/format'
import { formatPhone } from '@/lib/phone'
import { DEFAULT_ZONE, dateInZone, formatDay, formatTime } from '@/lib/time'
import {
  type AppointmentCard,
  type ClinicCard,
  type PrescriptionCard,
  type ProfileDetails,
  STATUS_LABELS,
} from '@/lib/types'

import { usePatientAuth } from './patient-auth'

export function ProfilePage() {
  const { profileId } = useParams()
  const { me } = usePatientAuth()
  const profile = useQuery({
    queryKey: ['patient-app', 'profile', profileId],
    queryFn: () => patientApi.get<ProfileDetails>(`/patient/profiles/${profileId}`),
    retry: false,
  })
  const hasOthers = (me?.profiles.length ?? 0) > 1

  if (profile.isPending) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (!profile.data) {
    return (
      <p className="text-sm text-muted-foreground">
        These records aren&apos;t available.{' '}
        <Link to="/patient" className="underline">
          Back
        </Link>
      </p>
    )
  }
  const p = profile.data

  return (
    <div className="flex flex-col gap-4">
      {hasOthers && (
        <Link to="/patient" className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Family members
        </Link>
      )}

      <Card>
        <CardContent className="flex items-center gap-4">
          <Avatar className="size-14">
            <AvatarFallback className="text-lg">{initials(p.full_name)}</AvatarFallback>
          </Avatar>
          <div className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold">{p.full_name}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {ageAndGender(p.age, p.gender) && <span>{ageAndGender(p.age, p.gender)}</span>}
              {p.blood_group && <Badge variant="outline">{p.blood_group}</Badge>}
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="visits">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="visits">Visits</TabsTrigger>
          <TabsTrigger value="clinics">Clinics</TabsTrigger>
          <TabsTrigger value="doctors">Doctors</TabsTrigger>
          <TabsTrigger value="prescriptions">Rx</TabsTrigger>
          <TabsTrigger value="reports">Reports</TabsTrigger>
        </TabsList>

        <TabsContent value="visits" className="flex flex-col gap-3">
          <Visits appointments={p.appointments} />
        </TabsContent>

        <TabsContent value="clinics" className="flex flex-col gap-3">
          {p.clinics.map((clinic) => (
            <ClinicItem key={clinic.id} clinic={clinic} />
          ))}
        </TabsContent>

        <TabsContent value="doctors" className="flex flex-col gap-3">
          {p.doctors.length === 0 ? (
            <Empty icon={Stethoscope} text="No doctors listed at your clinics yet." />
          ) : (
            p.doctors.map((doctor) => (
              <Card key={`${doctor.clinic_id}-${doctor.name}`}>
                <CardContent className="flex items-center gap-3">
                  <Avatar>
                    <AvatarFallback>{initials(doctor.name.replace(/^(Dr|Prof)\.\s*/, ''))}</AvatarFallback>
                  </Avatar>
                  <div>
                    <div className="font-medium">{doctor.name}</div>
                    <div className="text-sm text-muted-foreground">{doctor.clinic_name}</div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="prescriptions" className="flex flex-col gap-3">
          {p.prescriptions.length === 0 ? (
            <Empty
              icon={FileText}
              text="No prescriptions yet. When your doctor writes one, it will appear here and can be downloaded as a PDF."
            />
          ) : (
            p.prescriptions.map((rx) => <PrescriptionItem key={rx.id} profileId={p.id} rx={rx} />)
          )}
        </TabsContent>

        <TabsContent value="reports">
          <Empty
            icon={FlaskConical}
            text="No reports yet. Lab reports and scans your clinic uploads will appear here."
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ClinicItem({ clinic }: { clinic: ClinicCard }) {
  const address = [clinic.address, clinic.city, clinic.state, clinic.pincode].filter(Boolean).join(', ')
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="size-4 text-muted-foreground" />
          {clinic.name}
        </CardTitle>
        <CardDescription>Patient since {formatDate(clinic.patient_since)}</CardDescription>
      </CardHeader>
      {(address || clinic.phone || clinic.email) && (
        <CardContent className="flex flex-col gap-2 text-sm">
          {address && (
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${clinic.name}, ${address}`)}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-start gap-2 hover:underline"
            >
              <MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              {address}
            </a>
          )}
          {clinic.phone && (
            <a href={`tel:${clinic.phone}`} className="flex items-center gap-2 hover:underline">
              <Phone className="size-4 text-muted-foreground" />
              {formatPhone(clinic.phone)}
            </a>
          )}
          {clinic.email && (
            <a href={`mailto:${clinic.email}`} className="flex items-center gap-2 hover:underline">
              <Mail className="size-4 text-muted-foreground" />
              {clinic.email}
            </a>
          )}
        </CardContent>
      )}
    </Card>
  )
}

function Empty({ icon: Icon, text }: { icon: React.ElementType; text: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-8 text-center text-sm text-muted-foreground">
        <Icon className="size-8" />
        {text}
      </CardContent>
    </Card>
  )
}

// Clinics on Doctoo are in India for now; times are shown in clinic time.
const ZONE = DEFAULT_ZONE

function Visits({ appointments }: { appointments: AppointmentCard[] }) {
  const [now] = useState(() => Date.now())
  // Today's visit in progress, or bookings still ahead.
  const upcoming = appointments
    .filter(
      (a) =>
        a.status === 'arrived' ||
        a.status === 'in_consultation' ||
        (a.status === 'booked' && new Date(a.start_at).getTime() >= now - 3600_000),
    )
    .reverse()
  const past = appointments.filter((a) => !upcoming.includes(a))
  if (appointments.length === 0) {
    return <Empty icon={CalendarDays} text="No visits yet. Appointments booked at your clinic appear here." />
  }
  return (
    <>
      {upcoming.length > 0 && <h2 className="text-sm font-medium text-muted-foreground">Today & upcoming</h2>}
      {upcoming.map((a) => (
        <VisitItem key={a.id} visit={a} highlight />
      ))}
      {past.length > 0 && <h2 className="pt-2 text-sm font-medium text-muted-foreground">Past</h2>}
      {past.map((a) => (
        <VisitItem key={a.id} visit={a} />
      ))}
    </>
  )
}

function VisitItem({ visit: a, highlight }: { visit: AppointmentCard; highlight?: boolean }) {
  return (
    <Card className={highlight ? 'border-primary/40' : undefined}>
      <CardContent className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <div className="font-medium">
            {formatDay(dateInZone(a.start_at, ZONE), { weekday: 'short' })} ·{' '}
            {a.kind === 'walk_in' ? `Token #${a.token_number}` : formatTime(a.start_at, ZONE)}
          </div>
          <div className="text-sm text-muted-foreground">
            {a.doctor_name} · {a.clinic_name}
          </div>
          {a.reason && <div className="text-sm">{a.reason}</div>}
        </div>
        <Badge variant="outline">{STATUS_LABELS[a.status]}</Badge>
      </CardContent>
    </Card>
  )
}

function PrescriptionItem({ profileId, rx }: { profileId: string; rx: PrescriptionCard }) {
  const [downloading, setDownloading] = useState(false)
  async function download() {
    setDownloading(true)
    try {
      const blob = await patientApi.getBlob(`/patient/profiles/${profileId}/prescriptions/${rx.id}.pdf`)
      saveBlob(blob, `${rx.number}.pdf`)
    } finally {
      setDownloading(false)
    }
  }
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-medium">{rx.diagnosis || 'Prescription'}</div>
            <div className="text-sm text-muted-foreground">
              {formatDay(dateInZone(rx.completed_at, ZONE), { year: 'numeric' })} · {rx.doctor_name} ·{' '}
              {rx.clinic_name}
            </div>
          </div>
          <Badge variant="outline">{rx.number}</Badge>
        </div>
        {rx.medicines.length > 0 && (
          <ul className="list-inside list-disc text-sm">
            {rx.medicines.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        )}
        {rx.follow_up_date && (
          <div className="text-sm">
            Follow-up on <strong>{formatDay(rx.follow_up_date, { weekday: 'long' })}</strong>
          </div>
        )}
        <Button variant="outline" onClick={download} disabled={downloading}>
          <Download /> {downloading ? 'Downloading…' : 'Download PDF'}
        </Button>
      </CardContent>
    </Card>
  )
}
