import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldGroup } from '@/components/ui/field'
import { useAuth } from '@/features/auth/auth-context'
import { FormError } from '@/features/auth/FormError'
import { errorText } from '@/lib/errors'
import { nameField } from '@/features/auth/schemas'
import { api } from '@/lib/api'
import type { Clinic } from '@/lib/types'

// Empty inputs are sent as null so optional fields can be cleared.
const optional = (schema: z.ZodType<string>) =>
  z.union([z.literal(''), schema]).transform((v) => (v === '' ? null : v))

const schema = z.object({
  name: nameField,
  phone: optional(z.string().trim().max(20)),
  email: optional(z.email('Enter a valid email address')),
  address: optional(z.string().trim().max(500)),
  city: optional(z.string().trim().max(100)),
  state: optional(z.string().trim().max(100)),
  pincode: optional(z.string().regex(/^\d{6}$/, 'PIN code must be 6 digits')),
  gstin: optional(z.string().trim().regex(/^[0-9A-Za-z]{15}$/, 'GSTIN must be 15 characters')),
})
type FormInput = z.input<typeof schema>
type FormOutput = z.output<typeof schema>

function toFormValues(clinic: Clinic): FormInput {
  return {
    name: clinic.name,
    phone: clinic.phone ?? '',
    email: clinic.email ?? '',
    address: clinic.address ?? '',
    city: clinic.city ?? '',
    state: clinic.state ?? '',
    pincode: clinic.pincode ?? '',
    gstin: clinic.gstin ?? '',
  }
}

export function ClinicSettingsPage() {
  const { membership, reloadMe } = useAuth()
  const isOwner = membership?.role === 'owner'
  const queryClient = useQueryClient()
  const clinic = useQuery({
    queryKey: ['clinic'],
    queryFn: () => api.get<Clinic>('/clinics/current'),
  })
  const [error, setError] = useState<string>()
  const form = useForm<FormInput, unknown, FormOutput>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting, isDirty } = form.formState

  useEffect(() => {
    if (clinic.data) form.reset(toFormValues(clinic.data))
  }, [clinic.data, form])

  async function onSubmit(values: FormOutput) {
    setError(undefined)
    try {
      const updated = await api.patch<Clinic>('/clinics/current', values)
      queryClient.setQueryData(['clinic'], updated)
      await reloadMe() // clinic name appears in the sidebar
      toast.success('Clinic details saved')
    } catch (e) {
      setError(errorText(e))
    }
  }

  const field = (name: keyof FormInput, label: string, extra: object = {}) => (
    <TextField
      label={label}
      disabled={!isOwner}
      registration={form.register(name)}
      error={errors[name]}
      {...extra}
    />
  )

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Clinic settings</h1>
        <p className="text-muted-foreground">
          These details appear on prescriptions and invoices.
          {!isOwner && ' Only the clinic owner can change them.'}
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Clinic details</CardTitle>
          <CardDescription>Name, contact and tax details.</CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={form.handleSubmit(onSubmit)}>
            <FieldGroup>
              <FormError message={error} />
              {field('name', 'Clinic name')}
              <div className="grid gap-6 sm:grid-cols-2">
                {field('phone', 'Phone', { type: 'tel', autoComplete: 'tel' })}
                {field('email', 'Email', { type: 'email' })}
              </div>
              {field('address', 'Address')}
              <div className="grid gap-6 sm:grid-cols-3">
                {field('city', 'City')}
                {field('state', 'State')}
                {field('pincode', 'PIN code', { inputMode: 'numeric', maxLength: 6 })}
              </div>
              {field('gstin', 'GSTIN (optional)', {
                className: 'uppercase',
                maxLength: 15,
                description: 'Needed for GST invoices',
              })}
              {isOwner && (
                <div>
                  <Button type="submit" disabled={isSubmitting || !isDirty}>
                    {isSubmitting ? 'Saving…' : 'Save changes'}
                  </Button>
                </div>
              )}
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
