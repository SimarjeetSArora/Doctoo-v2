import { ChevronRight, Lock } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { patientApi } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { initials, todayIso } from '@/lib/format'
import type { ProfileSummary } from '@/lib/types'

import { usePatientAuth } from './patient-auth'

/** "Who are you?" — one mobile number can hold several family members. */
export function ProfilesPage() {
  const { me } = usePatientAuth()
  const profiles = me?.profiles ?? []

  // One confirmed person on this number: go straight to their records.
  if (profiles.length === 1 && profiles[0].verified) {
    return <Navigate to={`/patient/profile/${profiles[0].id}`} replace />
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Who&apos;s checking?</h1>
        <p className="text-sm text-muted-foreground">
          These people are registered with this mobile number at their clinics.
        </p>
      </div>
      {profiles.length === 0 && (
        <Card>
          <CardContent className="text-sm text-muted-foreground">
            No records found for this number anymore. Please contact your clinic.
          </CardContent>
        </Card>
      )}
      {profiles.map((profile) => (
        <ProfileRow key={profile.id} profile={profile} />
      ))}
    </div>
  )
}

function ProfileRow({ profile }: { profile: ProfileSummary }) {
  const { reloadMe } = usePatientAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [dob, setDob] = useState('')
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [today] = useState(todayIso)
  const clinics = `${profile.clinic_count} clinic${profile.clinic_count === 1 ? '' : 's'}`

  async function confirm(e: React.FormEvent) {
    e.preventDefault()
    if (!dob) return setError('Choose your date of birth')
    setBusy(true)
    setError(undefined)
    try {
      await patientApi.post(`/patient/profiles/${profile.id}/verify`, { date_of_birth: dob })
      await reloadMe()
      navigate(`/patient/profile/${profile.id}`)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const header = (
    <div className="flex items-center gap-3">
      <Avatar className="size-11">
        <AvatarFallback>{initials(profile.name)}</AvatarFallback>
      </Avatar>
      <div className="flex-1">
        <div className="font-medium">{profile.name}</div>
        <div className="text-sm text-muted-foreground">{clinics}</div>
      </div>
      {profile.verified ? (
        <ChevronRight className="size-5 text-muted-foreground" />
      ) : (
        <Lock className="size-4 text-muted-foreground" aria-label="Not confirmed yet" />
      )}
    </div>
  )

  if (profile.verified) {
    return (
      <Link to={`/patient/profile/${profile.id}`}>
        <Card className="transition-colors hover:border-primary/50">
          <CardContent>{header}</CardContent>
        </Card>
      </Link>
    )
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        {header}
        {!profile.can_verify ? (
          <p className="text-sm text-muted-foreground">
            Your clinic hasn&apos;t recorded a date of birth for this person yet. Ask them to add it,
            then you can open these records.
          </p>
        ) : !open ? (
          <Button variant="outline" onClick={() => setOpen(true)}>
            This is me — confirm date of birth
          </Button>
        ) : (
          <form onSubmit={confirm} className="flex flex-col gap-3">
            <Field data-invalid={!!error}>
              <FieldLabel htmlFor={`dob-${profile.id}`}>Date of birth</FieldLabel>
              <Input
                id={`dob-${profile.id}`}
                type="date"
                max={today}
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                autoFocus
              />
              <FieldError>{error}</FieldError>
            </Field>
            <Button type="submit" disabled={busy}>
              {busy ? 'Checking…' : 'Confirm'}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
