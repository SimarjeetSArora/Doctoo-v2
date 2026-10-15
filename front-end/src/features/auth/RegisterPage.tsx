import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { z } from 'zod'

import { PasswordField } from '@/components/PasswordField'
import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { FieldGroup, FieldLegend, FieldSet } from '@/components/ui/field'
import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import type { TokenResponse } from '@/lib/types'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { EmailVerificationFields } from './EmailVerificationFields'
import { FormError } from './FormError'
import { checkPhone, profileDefaults, profileFields, toProfile } from './profile'
import { NameFields, PhoneField } from './ProfileFields'
import { emailField, nameField, passwordField } from './schemas'
import { useCodeSender } from './use-code-sender'

const schema = z
  .object({
    ...profileFields,
    clinic_name: nameField,
    email: emailField,
    email_code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code from your email'),
    password: passwordField,
    confirm_password: z.string().min(1, 'Re-enter your password'),
  })
  .superRefine((values, ctx) => {
    checkPhone(values, ctx)
    if (values.confirm_password && values.password !== values.confirm_password) {
      ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: "Passwords don't match" })
    }
  })
type Values = z.infer<typeof schema>

/** Clinic owner sign-up: verifies the email with a code, then creates the account and clinic. */
export function RegisterPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string>()
  const codes = useCodeSender('register')

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      ...profileDefaults,
      clinic_name: '',
      email: '',
      email_code: '',
      password: '',
      confirm_password: '',
    },
  })
  const { errors, isSubmitting } = form.formState
  const password = useWatch({ control: form.control, name: 'password' })
  const email = (useWatch({ control: form.control, name: 'email' }) ?? '').trim().toLowerCase()

  async function onSubmit(values: Values) {
    setError(undefined)
    try {
      const tokens = await api.post<TokenResponse>('/auth/register', {
        ...toProfile(values),
        clinic_name: values.clinic_name,
        email: values.email,
        email_code: values.email_code,
        password: values.password,
      })
      await signIn(tokens)
      navigate('/', { replace: true })
    } catch (e) {
      const message = errorText(e)
      // Code problems (wrong / expired / too many tries) belong next to the code boxes.
      if (/code/i.test(message)) form.setError('email_code', { message }, { shouldFocus: true })
      else setError(message)
    }
  }

  function onInvalid() {
    if (codes.sentTo !== email) {
      form.setError('email', { message: 'Verify your email first: click "Send code"' })
    }
  }

  return (
    <AuthLayout
      wide
      title="Create your clinic account"
      description="Set up Doctoo for your clinic in a couple of minutes"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
            Log in
          </Link>
        </>
      }
    >
      <FormProvider {...form}>
        <form noValidate onSubmit={form.handleSubmit(onSubmit, onInvalid)}>
          <FieldGroup>
            <FormError message={error} />

            <FieldSet>
              <FieldLegend>About you</FieldLegend>
              <NameFields autoFocus />
              <PhoneField />
            </FieldSet>

            <FieldSet>
              <FieldLegend>Your clinic</FieldLegend>
              <TextField
                label="Clinic name"
                autoComplete="organization"
                placeholder="Sunrise Family Clinic"
                registration={form.register('clinic_name')}
                error={errors.clinic_name}
              />
            </FieldSet>

            <FieldSet>
              <FieldLegend>Login details</FieldLegend>
              <EmailVerificationFields sender={codes} />
              <PasswordField
                label="Password"
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
            </FieldSet>

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </Button>
          </FieldGroup>
        </form>
      </FormProvider>
    </AuthLayout>
  )
}
