import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  CircleAlert,
  Download,
  FileSignature,
  Loader2,
  MessageCircle,
  Phone,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useClinicZone } from '@/features/appointments/hooks'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { openBlob } from '@/lib/files'
import { ageAndGender } from '@/lib/format'
import { formatPhone } from '@/lib/phone'
import { addDays, todayInZone } from '@/lib/time'
import type { Visit } from '@/lib/types'

import { type Draft, toDraft, toPayload, VITAL_FIELDS } from './draft'
import { PrescriptionEditor } from './PrescriptionEditor'
import { VisitSummaryView } from './VisitSummaryView'

type SaveState = 'saved' | 'unsaved' | 'saving' | 'error'

export function ConsultationPage() {
  const { visitId } = useParams()
  const visit = useQuery({
    queryKey: ['visit', visitId],
    queryFn: () => api.get<Visit>(`/visits/${visitId}`),
  })
  if (visit.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (!visit.data) return <p className="text-muted-foreground">Consultation not found.</p>
  return visit.data.can_edit ? <Editor visit={visit.data} /> : <Finished visit={visit.data} />
}

function PatientHeader({ visit, right }: { visit: Visit; right?: React.ReactNode }) {
  const p = visit.patient
  return (
    <div className="flex flex-col gap-4">
      <Link
        to={`/patients/${p.id}`}
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {p.full_name}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">{p.full_name}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            {ageAndGender(p.age, p.gender) && <span>{ageAndGender(p.age, p.gender)}</span>}
            <span className="flex items-center gap-1">
              <Phone className="size-3.5" />
              {formatPhone(p.phone)}
            </span>
            {p.blood_group && <Badge variant="outline">{p.blood_group}</Badge>}
            <span>· {visit.doctor_name}</span>
          </div>
        </div>
        {right}
      </div>
      {p.notes && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/40">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-400" />
          <span>
            <strong>Alerts:</strong> {p.notes}
          </span>
        </div>
      )}
    </div>
  )
}

function Editor({ visit }: { visit: Visit }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const zone = useClinicZone()
  const [today] = useState(() => todayInZone(zone))
  const [draft, setDraft] = useState<Draft>(() => toDraft(visit))
  const [saveState, setSaveState] = useState<SaveState>('saved')
  const [confirming, setConfirming] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const latest = useRef(draft)
  const dirty = useRef(false)

  const save = useCallback(async () => {
    if (!dirty.current) return true
    dirty.current = false
    setSaveState('saving')
    try {
      await api.patch<Visit>(`/visits/${visit.id}`, toPayload(latest.current))
      setSaveState(dirty.current ? 'unsaved' : 'saved')
      return true
    } catch (e) {
      dirty.current = true
      setSaveState('error')
      toast.error(errorText(e))
      return false
    }
  }, [visit.id])

  // Save automatically shortly after the doctor stops typing.
  useEffect(() => {
    if (!dirty.current) return
    const timer = setTimeout(() => void save(), 1200)
    return () => clearTimeout(timer)
  }, [draft, save])

  function change(update: Partial<Draft>) {
    setDraft((current) => {
      const next = { ...current, ...update }
      latest.current = next
      return next
    })
    dirty.current = true
    setSaveState('unsaved')
  }

  async function finish() {
    setFinishing(true)
    if (!(await save())) {
      setFinishing(false)
      return
    }
    try {
      const done = await api.post<Visit>(`/visits/${visit.id}/complete`)
      queryClient.setQueryData(['visit', visit.id], done)
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['visits'] })
      toast.success(`Prescription ${done.prescription_number} saved`)
      setConfirming(false)
      navigate(`/consultations/${visit.id}`, { replace: true })
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setFinishing(false)
    }
  }

  const status = {
    saved: 'All changes saved',
    unsaved: 'Unsaved changes…',
    saving: 'Saving…',
    error: 'Couldn’t save — retrying when you edit',
  }[saveState]

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 pb-24">
      <PatientHeader
        visit={visit}
        right={
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground" aria-live="polite">
              {saveState === 'saving' && <Loader2 className="size-3.5 animate-spin" />}
              {status}
            </span>
            <Button
              variant="outline"
              onClick={async () => {
                if (await save()) openBlob(await api.getBlob(`/visits/${visit.id}/prescription.pdf`))
              }}
            >
              <Download /> Preview PDF
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Vitals</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Field>
            <FieldLabel htmlFor="bp_systolic">BP (mmHg)</FieldLabel>
            <div className="flex items-center gap-1">
              <Input
                id="bp_systolic"
                inputMode="numeric"
                placeholder="120"
                aria-label="Systolic"
                value={draft.vitals.bp_systolic}
                onChange={(e) => change({ vitals: { ...draft.vitals, bp_systolic: e.target.value } })}
              />
              <span className="text-muted-foreground">/</span>
              <Input
                inputMode="numeric"
                placeholder="80"
                aria-label="Diastolic"
                value={draft.vitals.bp_diastolic}
                onChange={(e) => change({ vitals: { ...draft.vitals, bp_diastolic: e.target.value } })}
              />
            </div>
          </Field>
          {VITAL_FIELDS.map((f) => (
            <Field key={f.key}>
              <FieldLabel htmlFor={f.key}>
                {f.label} <span className="text-muted-foreground">({f.unit})</span>
              </FieldLabel>
              <Input
                id={f.key}
                type="number"
                inputMode="decimal"
                step={f.step ?? '1'}
                value={draft.vitals[f.key]}
                onChange={(e) => change({ vitals: { ...draft.vitals, [f.key]: e.target.value } })}
              />
            </Field>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notes</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field>
            <FieldLabel htmlFor="complaints">Complaints</FieldLabel>
            <Textarea
              id="complaints"
              rows={2}
              autoFocus
              placeholder="Fever and sore throat for 2 days…"
              value={draft.complaints}
              onChange={(e) => change({ complaints: e.target.value })}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="examination">Examination findings</FieldLabel>
            <Textarea
              id="examination"
              rows={2}
              value={draft.examination}
              onChange={(e) => change({ examination: e.target.value })}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="diagnosis">Diagnosis</FieldLabel>
            <Input
              id="diagnosis"
              placeholder="e.g. Acute pharyngitis"
              value={draft.diagnosis}
              onChange={(e) => change({ diagnosis: e.target.value })}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-2xl leading-none">℞</span> Prescription
          </CardTitle>
        </CardHeader>
        <CardContent>
          <PrescriptionEditor items={draft.items} onChange={(items) => change({ items })} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Advice & follow-up</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field>
            <FieldLabel htmlFor="advice">Advice</FieldLabel>
            <Textarea
              id="advice"
              rows={2}
              placeholder="Plenty of fluids, rest…"
              value={draft.advice}
              onChange={(e) => change({ advice: e.target.value })}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="follow_up_date">Follow-up</FieldLabel>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                id="follow_up_date"
                type="date"
                min={today}
                className="w-44"
                value={draft.follow_up_date}
                onChange={(e) => change({ follow_up_date: e.target.value })}
              />
              {[
                ['3 days', 3],
                ['1 week', 7],
                ['2 weeks', 14],
                ['1 month', 30],
              ].map(([label, days]) => (
                <Button
                  key={label}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => change({ follow_up_date: addDays(today, Number(days)) })}
                >
                  +{label}
                </Button>
              ))}
              {draft.follow_up_date && (
                <Button type="button" variant="ghost" size="sm" onClick={() => change({ follow_up_date: '' })}>
                  Clear
                </Button>
              )}
            </div>
          </Field>
        </CardContent>
      </Card>

      <div className="sticky bottom-4 flex justify-end">
        <Button size="lg" className="shadow-lg" onClick={() => setConfirming(true)}>
          <FileSignature /> Finish & sign
        </Button>
      </div>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Finish this consultation?</DialogTitle>
            <DialogDescription>
              The prescription gets its number and the record is locked — medical records can’t be
              changed afterwards. The appointment is marked completed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(false)}>
              Keep editing
            </Button>
            <Button onClick={finish} disabled={finishing}>
              {finishing ? 'Finishing…' : 'Finish & sign'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function Finished({ visit }: { visit: Visit }) {
  const [sharing, setSharing] = useState(false)
  const done = visit.status === 'completed'

  async function share() {
    setSharing(true)
    try {
      const result = await api.post<{ sent_to: string }>(`/visits/${visit.id}/share`)
      toast.success(`Prescription sent on WhatsApp to ${formatPhone(result.sent_to)}`)
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setSharing(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PatientHeader
        visit={visit}
        right={
          done ? (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={async () => openBlob(await api.getBlob(`/visits/${visit.id}/prescription.pdf`))}
              >
                <Download /> Prescription PDF
              </Button>
              <Button
                onClick={share}
                disabled={sharing || !visit.patient.messaging_consent}
                title={visit.patient.messaging_consent ? undefined : 'The patient hasn’t agreed to WhatsApp messages'}
              >
                <MessageCircle /> {sharing ? 'Sending…' : 'Send on WhatsApp'}
              </Button>
            </div>
          ) : (
            <Badge variant="secondary">In progress — only {visit.doctor_name} can edit</Badge>
          )
        }
      />
      {done && !visit.patient.messaging_consent && (
        <p className="text-sm text-muted-foreground">
          To send prescriptions on WhatsApp, record the patient’s consent on their{' '}
          <Link to={`/patients/${visit.patient.id}/edit`} className="underline">
            details page
          </Link>
          .
        </p>
      )}
      <VisitSummaryView visit={visit} />
    </div>
  )
}

