import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'

import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'

import { AuthLayout } from './AuthLayout'
import { FormError } from './FormError'
import { emailField } from './schemas'

const schema = z.object({ email: emailField })
type Values = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const [sentTo, setSentTo] = useState<string>()
  const [error, setError] = useState<string>()
  const form = useForm<Values>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState

  async function onSubmit(values: Values) {
    setError(undefined)
    try {
      await api.post('/auth/password/forgot', values)
      setSentTo(values.email)
    } catch (e) {
      setError(errorText(e))
    }
  }

  const backToLogin = (
    <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
      Back to log in
    </Link>
  )

  if (sentTo) {
    return (
      <AuthLayout title="Check your email" footer={backToLogin}>
        <div className="flex flex-col items-center gap-3 text-center text-sm text-muted-foreground">
          <MailCheck className="size-10 text-primary" />
          <p>
            If an account exists for <span className="font-medium text-foreground">{sentTo}</span>,
            we&apos;ve sent a link to reset your password. It expires in 1 hour.
          </p>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      description="Enter your email and we'll send you a reset link"
      footer={backToLogin}
    >
      <form noValidate onSubmit={form.handleSubmit(onSubmit)}>
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
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Sending…' : 'Send reset link'}
          </Button>
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
