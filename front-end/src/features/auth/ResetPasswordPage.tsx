import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { PasswordField } from '@/components/PasswordField'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { api } from '@/lib/api'
import type { TokenResponse } from '@/lib/types'
import { errorText } from '@/lib/errors'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { FormError } from './FormError'
import { passwordField } from './schemas'

const schema = z
  .object({ new_password: passwordField, confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, {
    message: "Passwords don't match",
    path: ['confirm'],
  })
type Values = z.infer<typeof schema>

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string>()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: '', confirm: '' },
  })
  const { errors, isSubmitting } = form.formState
  const newPassword = useWatch({ control: form.control, name: 'new_password' })

  async function onSubmit({ new_password }: Values) {
    setError(undefined)
    try {
      await signIn(await api.post<TokenResponse>('/auth/password/reset', { token, new_password }))
      navigate('/', { replace: true })
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <AuthLayout
      title="Choose a new password"
      description="You'll be logged out of all other devices."
      footer={
        <Link to="/forgot-password" className="underline underline-offset-4">
          Need a new link?
        </Link>
      }
    >
      <form noValidate onSubmit={form.handleSubmit(onSubmit)}>
        <FieldGroup>
          <FormError message={token ? error : 'This reset link is missing its token.'} />
          <PasswordField
            label="New password"
            autoComplete="new-password"
            autoFocus
            registration={form.register('new_password')}
            error={errors.new_password}
            strengthOf={newPassword}
          />
          <PasswordField
            label="Confirm new password"
            autoComplete="new-password"
            registration={form.register('confirm')}
            error={errors.confirm}
          />
          <Button type="submit" disabled={isSubmitting || !token}>
            {isSubmitting ? 'Saving…' : 'Set new password'}
          </Button>
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
