import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { z } from 'zod'

import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { api } from '@/lib/api'
import type { TokenResponse } from '@/lib/types'
import { errorText } from '@/lib/errors'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { FormError } from './FormError'
import { emailField, nameField, passwordField } from './schemas'

const schema = z.object({
  full_name: nameField,
  clinic_name: nameField,
  email: emailField,
  password: passwordField,
})
type Values = z.infer<typeof schema>

/** Clinic owner sign-up: creates their account and clinic in one step. */
export function RegisterPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string>()

  const form = useForm<Values>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState

  async function finish(request: Promise<TokenResponse>) {
    setError(undefined)
    try {
      await signIn(await request)
      navigate('/', { replace: true })
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <AuthLayout
      title="Create your clinic account"
      description="Set up Doctoo for your clinic in under a minute"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
            Log in
          </Link>
        </>
      }
    >
      <form
        noValidate
        onSubmit={form.handleSubmit((values) =>
          finish(api.post<TokenResponse>('/auth/register', values)),
        )}
      >
        <FieldGroup>
          <FormError message={error} />
          <TextField
            label="Your full name"
            autoComplete="name"
            autoFocus
            placeholder="Dr. Anita Sharma"
            registration={form.register('full_name')}
            error={errors.full_name}
          />
          <TextField
            label="Clinic name"
            autoComplete="organization"
            placeholder="Sunrise Family Clinic"
            registration={form.register('clinic_name')}
            error={errors.clinic_name}
          />
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            registration={form.register('email')}
            error={errors.email}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            description="At least 8 characters"
            registration={form.register('password')}
            error={errors.password}
          />
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
