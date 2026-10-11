import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'
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
import { emailField } from './schemas'

const schema = z.object({
  email: emailField,
  password: z.string().min(1, 'Enter your password'),
})
type Values = z.infer<typeof schema>

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [error, setError] = useState<string>()

  const form = useForm<Values>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState

  async function finish(request: Promise<TokenResponse>) {
    setError(undefined)
    try {
      await signIn(await request)
      navigate(from, { replace: true })
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      description="Log in to your clinic"
      footer={
        <>
          New to Doctoo?{' '}
          <Link to="/register" className="font-medium text-foreground underline underline-offset-4">
            Create your clinic account
          </Link>
        </>
      }
    >
      <form
        noValidate
        onSubmit={form.handleSubmit((values) =>
          finish(api.post<TokenResponse>('/auth/login', values)),
        )}
      >
        <FieldGroup>
          <FormError message={error} />
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            autoFocus
            registration={form.register('email')}
            error={errors.email}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            registration={form.register('password')}
            error={errors.password}
          />
          <div className="-mt-3 text-right text-sm">
            <Link to="/forgot-password" className="text-muted-foreground hover:underline">
              Forgot password?
            </Link>
          </div>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Logging in…' : 'Log in'}
          </Button>
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
