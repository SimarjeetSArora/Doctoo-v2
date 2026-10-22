import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { Controller, FormProvider, useForm } from 'react-hook-form'
import { z } from 'zod'

import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { FormError } from '@/features/auth/FormError'
import { checkPhone } from '@/features/auth/profile'
import { PhoneField } from '@/features/auth/ProfileFields'
import { emailField, nameField } from '@/features/auth/schemas'
import { DEFAULT_COUNTRY } from '@/lib/countries'
import { errorText } from '@/lib/errors'
import { todayIso } from '@/lib/format'
import { splitE164, toE164 } from '@/lib/phone'
import { BLOOD_GROUPS, GENDER_LABELS, type Gender, type Patient } from '@/lib/types'

const NONE = 'none' // Select can't hold an empty value

const schema = z
  .object({
    full_name: nameField,
    country: z.string(),
    phone_number: z.string().trim().min(1, 'Required'),
    email: z.union([z.literal(''), emailField]),
    date_of_birth: z
      .string()
      .refine((v) => !v || v <= new Date().toISOString().slice(0, 10), "Can't be in the future"),
    gender: z.string(),
    blood_group: z.string(),
    address: z.string().max(500),
    abha_number: z
      .string()
      .refine((v) => !v || /^\d{14}$/.test(v.replace(/[\s-]/g, '')), 'ABHA number has 14 digits'),
    notes: z.string().max(2000),
    messaging_consent: z.boolean(),
  })
  .superRefine((values, ctx) => checkPhone(values, ctx))
export type PatientFormValues = z.infer<typeof schema>

function toFormValues(patient?: Patient): PatientFormValues {
  const phone = patient ? splitE164(patient.phone) : { country: DEFAULT_COUNTRY, national: '' }
  return {
    full_name: patient?.full_name ?? '',
    country: phone.country,
    phone_number: phone.national,
    email: patient?.email ?? '',
    date_of_birth: patient?.date_of_birth ?? '',
    gender: patient?.gender ?? NONE,
    blood_group: patient?.blood_group ?? NONE,
    address: patient?.address ?? '',
    abha_number: patient?.abha_number ?? '',
    notes: patient?.notes ?? '',
    messaging_consent: patient?.messaging_consent ?? false,
  }
}

/** What the API expects (blank optional fields become null). */
function toPatientPayload(v: PatientFormValues) {
  const orNull = (s: string) => (s.trim() && s !== NONE ? s.trim() : null)
  return {
    full_name: v.full_name,
    phone: toE164(v.country, v.phone_number),
    email: orNull(v.email),
    date_of_birth: orNull(v.date_of_birth),
    gender: orNull(v.gender) as Gender | null,
    blood_group: orNull(v.blood_group),
    address: orNull(v.address),
    abha_number: orNull(v.abha_number),
    notes: orNull(v.notes),
    messaging_consent: v.messaging_consent,
  }
}

export function PatientForm({
  patient,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  patient?: Patient
  submitLabel: string
  onSubmit: (payload: ReturnType<typeof toPatientPayload>) => Promise<void>
  onCancel: () => void
}) {
  const [error, setError] = useState<string>()
  const [today] = useState(todayIso)
  const form = useForm<PatientFormValues>({
    resolver: zodResolver(schema),
    defaultValues: toFormValues(patient),
  })
  const { errors, isSubmitting } = form.formState

  async function submit(values: PatientFormValues) {
    setError(undefined)
    try {
      await onSubmit(toPatientPayload(values))
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <FormProvider {...form}>
      <form noValidate onSubmit={form.handleSubmit(submit)}>
        <FieldGroup>
          <FormError message={error} />

          <FieldSet>
            <FieldLegend>Patient details</FieldLegend>
            <TextField
              label="Full name"
              autoFocus={!patient}
              registration={form.register('full_name')}
              error={errors.full_name}
            />
            <PhoneField />
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField
                label="Date of birth"
                type="date"
                max={today}
                description="Needed for the patient app"
                registration={form.register('date_of_birth')}
                error={errors.date_of_birth}
              />
              <SelectField name="gender" label="Gender" control={form.control}>
                {(Object.keys(GENDER_LABELS) as Gender[]).map((g) => (
                  <SelectItem key={g} value={g}>
                    {GENDER_LABELS[g]}
                  </SelectItem>
                ))}
              </SelectField>
              <SelectField name="blood_group" label="Blood group" control={form.control}>
                {BLOOD_GROUPS.map((b) => (
                  <SelectItem key={b} value={b}>
                    {b}
                  </SelectItem>
                ))}
              </SelectField>
            </div>
          </FieldSet>

          <FieldSet>
            <FieldLegend>Contact & IDs (optional)</FieldLegend>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Email"
                type="email"
                registration={form.register('email')}
                error={errors.email}
              />
              <TextField
                label="ABHA number"
                placeholder="12-3456-7890-1234"
                inputMode="numeric"
                registration={form.register('abha_number')}
                error={errors.abha_number}
              />
            </div>
            <TextField label="Address" registration={form.register('address')} error={errors.address} />
          </FieldSet>

          <FieldSet>
            <FieldLegend>Medical notes</FieldLegend>
            <Field data-invalid={!!errors.notes}>
              <FieldLabel htmlFor="notes">Allergies, chronic conditions, etc.</FieldLabel>
              <Textarea id="notes" rows={3} {...form.register('notes')} />
              <FieldError errors={[errors.notes]} />
            </Field>
          </FieldSet>

          <Controller
            control={form.control}
            name="messaging_consent"
            render={({ field }) => (
              <Field orientation="horizontal">
                <Checkbox
                  id="messaging_consent"
                  checked={field.value}
                  onCheckedChange={(checked) => field.onChange(checked === true)}
                />
                <FieldContent>
                  <FieldLabel htmlFor="messaging_consent">
                    Patient agrees to receive WhatsApp / SMS messages
                  </FieldLabel>
                  <FieldDescription>
                    Prescriptions, reports and reminders. Required before sending them (DPDP Act).
                  </FieldDescription>
                </FieldContent>
              </Field>
            )}
          />

          <div className="flex gap-3">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : submitLabel}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </FieldGroup>
      </form>
    </FormProvider>
  )
}

function SelectField({
  name,
  label,
  control,
  children,
}: {
  name: 'gender' | 'blood_group'
  label: string
  control: ReturnType<typeof useForm<PatientFormValues>>['control']
  children: React.ReactNode
}) {
  return (
    <Field>
      <FieldLabel htmlFor={name}>{label}</FieldLabel>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select value={field.value} onValueChange={field.onChange}>
            <SelectTrigger id={name} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>Not specified</SelectItem>
              {children}
            </SelectContent>
          </Select>
        )}
      />
    </Field>
  )
}
