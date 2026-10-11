import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { api } from '@/lib/api'
import { type InvitationLookup, ROLE_LABELS, type TokenResponse } from '@/lib/types'
import { errorText } from '@/lib/errors'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { FormError } from './FormError'
import { FullPageSpinner } from './guards'
import { nameField, passwordField } from './schemas'

/** Page opened from the invitation email: join a clinic's team. */
export function InvitePage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const lookup = useQuery({
    queryKey: ['invitation', token],
    queryFn: () =>
      api.get<InvitationLookup>(`/invitations/lookup?token=${encodeURIComponent(token)}`),
    enabled: !!token,
    retry: false,
  })

  if (token && lookup.isPending) return <FullPageSpinner />
  if (!token || !lookup.data) {
    return (
      <AuthLayout
        title="Invitation not valid"
        description="This invitation link is invalid, already used, or has expired. Ask the clinic owner to send a new one."
        footer={
          <Link to="/login" className="underline underline-offset-4">
            Go to log in
          </Link>
        }
      >
        {null}
      </AuthLayout>
    )
  }
  return <AcceptInvitation token={token} invitation={lookup.data} />
}

function AcceptInvitation({ token, invitation }: { token: string; invitation: InvitationLookup }) {
  const { signIn, switchClinic } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string>()

  const schema = z.object({
    full_name: invitation.needs_name ? nameField : z.string().optional(),
    password: invitation.needs_password ? passwordField : z.string().optional(),
  })
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState

  async function accept(body: Record<string, unknown>) {
    setError(undefined)
    try {
      const tokens = await api.post<TokenResponse>('/invitations/accept', { token, ...body })
      switchClinic(invitation.clinic_id)
      await signIn(tokens)
      navigate('/', { replace: true })
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <AuthLayout
      title={`Join ${invitation.clinic_name}`}
      description={
        <>
          {invitation.invited_by_name} invited <strong>{invitation.email}</strong> to join as{' '}
          <strong>{ROLE_LABELS[invitation.role]}</strong>.
        </>
      }
    >
      <form
        noValidate
        onSubmit={form.handleSubmit((values) =>
          accept({ full_name: values.full_name || null, password: values.password || null }),
        )}
      >
        <FieldGroup>
          <FormError message={error} />
          {invitation.needs_name && (
            <TextField
              label="Your full name"
              autoComplete="name"
              autoFocus
              registration={form.register('full_name')}
              error={errors.full_name}
            />
          )}
          {invitation.needs_password && (
            <TextField
              label="Choose a password"
              type="password"
              autoComplete="new-password"
              description="At least 8 characters"
              registration={form.register('password')}
              error={errors.password}
            />
          )}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Joining…' : `Join ${invitation.clinic_name}`}
          </Button>
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
