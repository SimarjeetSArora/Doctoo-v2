import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, FileText, FlaskConical, Mail, MapPin, Phone, Stethoscope } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { patientApi } from '@/lib/api'
import { ageAndGender, formatDate, initials } from '@/lib/format'
import { formatPhone } from '@/lib/phone'
import type { ClinicCard, ProfileDetails } from '@/lib/types'

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

      <Tabs defaultValue="clinics">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="clinics">Clinics</TabsTrigger>
          <TabsTrigger value="doctors">Doctors</TabsTrigger>
          <TabsTrigger value="prescriptions">Rx</TabsTrigger>
          <TabsTrigger value="reports">Reports</TabsTrigger>
        </TabsList>

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

        <TabsContent value="prescriptions">
          <Empty
            icon={FileText}
            text="No prescriptions yet. When your doctor writes one, it will appear here and can be downloaded as a PDF."
          />
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
