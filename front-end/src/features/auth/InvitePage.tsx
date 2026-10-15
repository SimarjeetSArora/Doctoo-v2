import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { Smartphone } from 'lucide-react'
import { useMemo, useState } from 'react'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { PasswordField } from '@/components/PasswordField'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { api, ApiError } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { formatPhone } from '@/lib/phone'
import { type InvitationLookup, ROLE_LABELS, type TokenResponse } from '@/lib/types'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { EmailVerificationFields } from './EmailVerificationFields'
import { FormError } from './FormError'
import { FullPageSpinner } from './guards'
import {
  checkPhone,
  type ProfileFormValues,
  profileDefaults,
  profileFields,
  toProfile,
} from './profile'
import { NameFields, PhoneField } from './ProfileFields'
import { emailField, passwordField } from './schemas'
import { useCodeSender } from './use-code-sender'

/** Page opened from the invitation email or SMS: join a clinic's team. */
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
    // 409 = a specific reason we can't continue (e.g. unverified number); otherwise invalid link.
    const reason =
      lookup.error instanceof ApiError && lookup.error.status === 409
        ? lookup.error.message
        : 'This invitation link is invalid, already used, or has expired. Ask the clinic owner to send a new one.'
    return (
      <AuthLayout
        title="Can't use this invitation"
        description={reason}
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
  const codes = useCodeSender('register')
  const byPhone = invitation.channel === 'phone'
  const invitedAs = byPhone ? formatPhone(invitation.phone) : invitation.email

  const schema = useMemo(() => inviteSchema(invitation), [invitation])
  const form = useForm<InviteValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      ...profileDefaults,
      password: '',
      confirm_password: '',
      email: '',
      email_code: '',
    },
  })
  const { errors, isSubmitting } = form.formState
  const password = useWatch({ control: form.control, name: 'password' })

  async function onSubmit(values: InviteValues) {
    setError(undefined)
    let profile = null
    if (invitation.needs_name && byPhone) {
      // The number is the one the invitation was texted to.
      profile = {
        salutation: values.salutation,
        first_name: values.first_name,
        middle_name: values.middle_name || null,
        last_name: values.last_name,
        phone: invitation.phone,
      }
    } else if (invitation.needs_name) {
      profile = toProfile(values as ProfileFormValues)
    }
    try {
      const tokens = await api.post<TokenResponse>('/invitations/accept', {
        token,
        profile,
        password: values.password || null,
        ...(invitation.needs_email ? { email: values.email, email_code: values.email_code } : {}),
      })
      switchClinic(invitation.clinic_id)
      await signIn(tokens)
      navigate('/', { replace: true })
    } catch (e) {
      const message = errorText(e)
      if (invitation.needs_email && /code/i.test(message)) form.setError('email_code', { message })
      else setError(message)
    }
  }

  function onInvalid() {
    const email = (form.getValues('email') ?? '').trim().toLowerCase()
    if (invitation.needs_email && codes.sentTo !== email) {
      form.setError('email', { message: 'Verify your email first: click "Send code"' })
    }
  }

  return (
    <AuthLayout
      wide={invitation.needs_name}
      title={`Join ${invitation.clinic_name}`}
      description={
        <>
          {invitation.invited_by_name} invited <strong>{invitedAs}</strong> to join as{' '}
          <strong>{ROLE_LABELS[invitation.role]}</strong>.
        </>
      }
    >
      <FormProvider {...form}>
        <form noValidate onSubmit={form.handleSubmit(onSubmit, onInvalid)}>
          <FieldGroup>
            <FormError message={error} />
            {invitation.needs_name && (
              <>
                <NameFields autoFocus />
                {byPhone ? (
                  <Field>
                    <FieldLabel>Mobile number</FieldLabel>
                    <div className="flex h-9 items-center gap-2 rounded-md border bg-muted/50 px-3 text-sm">
                      <Smartphone className="size-4 text-muted-foreground" />
                      {formatPhone(invitation.phone)}
                    </div>
                    <FieldDescription>Confirmed by the invitation link we sent to this number.</FieldDescription>
                  </Field>
                ) : (
                  <PhoneField />
                )}
              </>
            )}
            {invitation.needs_email && <EmailVerificationFields sender={codes} />}
            {invitation.needs_password && (
              <>
                <PasswordField
                  label="Choose a password"
                  autoComplete="new-password"
                  registration={form.register('password')}
                  error={errors.password}
                  strengthOf={password}
                />
                <PasswordField
                  label="Confirm password"
                  autoComplete="new-password"
                  registration={form.register('confirm_password')}
                  error={errors.confirm_password}
                />
              </>
            )}
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Joining…' : `Join ${invitation.clinic_name}`}
            </Button>
          </FieldGroup>
        </form>
      </FormProvider>
    </AuthLayout>
  )
}

type InviteValues = Partial<ProfileFormValues> & {
  password?: string
  confirm_password?: string
  email?: string
  email_code?: string
}

/**
 * New users give their details and a password (plus a verified email if invited by SMS);
 * never-verified accounts just set a password; verified accounts just click Join.
 */
function inviteSchema(invitation: InvitationLookup): z.ZodType<InviteValues, InviteValues> {
  const byPhone = invitation.channel === 'phone'
  const password = invitation.needs_password
    ? { password: passwordField, confirm_password: z.string().min(1, 'Re-enter your password') }
    : {}
  const email = invitation.needs_email
    ? {
        email: emailField,
        email_code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code from your email'),
      }
    : {}
  // Invited by SMS: the number comes from the invitation, so the phone inputs aren't shown.
  const profile = invitation.needs_name
    ? byPhone
      ? { ...profileFields, country: z.string().optional(), phone_number: z.string().optional() }
      : profileFields
    : {}
  return z
    .object({ ...profile, ...email, ...password })
    .superRefine((values, ctx) => {
      const v = values as InviteValues
      if (invitation.needs_name && !byPhone) checkPhone(v as ProfileFormValues, ctx)
      if (invitation.needs_password && v.confirm_password && v.password !== v.confirm_password) {
        ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: "Passwords don't match" })
      }
    }) as unknown as z.ZodType<InviteValues, InviteValues>
}
