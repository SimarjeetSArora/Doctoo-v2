import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router'
import { z } from 'zod'

import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { api } from '@/lib/api'
import type { Clinic } from '@/lib/types'
import { errorText } from '@/lib/errors'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { FormError } from './FormError'
import { nameField } from './schemas'

const schema = z.object({ name: nameField })
type Values = z.infer<typeof schema>

/** Shown to signed-in users who no longer belong to any active clinic. */
export function OnboardingPage() {
  const { me, membership, reloadMe, switchClinic, signOut } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string>()
  const form = useForm<Values>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState

  if (membership) return <Navigate to="/" replace />

  async function onSubmit(values: Values) {
    setError(undefined)
    try {
      const clinic = await api.post<Clinic>('/clinics', values)
      switchClinic(clinic.id)
      await reloadMe()
      navigate('/', { replace: true })
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <AuthLayout
      title={`Welcome, ${me?.user.first_name ?? ''}!`}
      description="You aren't part of any clinic right now. Create your own, or open the invitation link a clinic owner emailed you."
      footer={
        <button className="underline underline-offset-4" onClick={() => signOut()}>
          Log out
        </button>
      }
    >
      <form noValidate onSubmit={form.handleSubmit(onSubmit)}>
        <FieldGroup>
          <FormError message={error} />
          <TextField
            label="Clinic name"
            autoComplete="organization"
            autoFocus
            placeholder="Sunrise Family Clinic"
            registration={form.register('name')}
            error={errors.name}
          />
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating…' : 'Create clinic'}
          </Button>
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
