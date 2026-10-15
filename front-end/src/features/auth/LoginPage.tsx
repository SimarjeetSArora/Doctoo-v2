import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { CircleCheck } from 'lucide-react'
import { useRef, useState } from 'react'
import { Controller, FormProvider, type Resolver, useForm, useWatch } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'

import { CodeInput } from '@/components/CodeInput'
import { SegmentedToggle } from '@/components/SegmentedToggle'
import { PasswordField } from '@/components/PasswordField'
import { TextField } from '@/components/TextField'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { api } from '@/lib/api'
import { CONTACT_OPTIONS, DELIVERY_OPTIONS } from '@/lib/contact-options'
import { DEFAULT_COUNTRY } from '@/lib/countries'
import { errorText } from '@/lib/errors'
import { toE164 } from '@/lib/phone'
import type { AuthOptions, OtpChannel, PhoneDelivery, TokenResponse } from '@/lib/types'

import { useAuth } from './auth-context'
import { AuthLayout } from './AuthLayout'
import { FormError } from './FormError'
import { checkPhone } from './profile'
import { PhoneField } from './ProfileFields'
import { emailField } from './schemas'
import { useCodeSender } from './use-code-sender'

type Method = 'password' | 'code'

type Values = {
  email: string
  country: string
  phone_number: string
  password: string
  code: string
}

/** Only the fields for the chosen identifier and method are validated. */
function loginSchema(via: OtpChannel, method: Method) {
  return z
    .object({
      email: via === 'email' ? emailField : z.string(),
      country: z.string(),
      phone_number: z.string(),
      password: method === 'password' ? z.string().min(1, 'Enter your password') : z.string(),
      code:
        method === 'code' ? z.string().regex(/^\d{6}$/, 'Enter the 6-digit code') : z.string(),
    })
    .superRefine((values, ctx) => {
      if (via === 'phone') checkPhone(values, ctx)
    })
}

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [error, setError] = useState<string>()
  const [via, setVia] = useState<OtpChannel>('email')
  const [method, setMethod] = useState<Method>('password')
  const codes = useCodeSender('login')
  const options = useQuery({
    queryKey: ['auth-options'],
    queryFn: () => api.get<AuthOptions>('/auth/options'),
    staleTime: Infinity,
  })
  const phoneChannels = options.data?.phone_code_channels ?? ['whatsapp']
  const [chosenDelivery, setDelivery] = useState<PhoneDelivery>('whatsapp')
  const delivery = phoneChannels.includes(chosenDelivery) ? chosenDelivery : phoneChannels[0]

  // The resolver reads the current choices, so validation follows the toggles.
  const choices = useRef({ via, method })
  const resolver: Resolver<Values> = (values, context, options) =>
    zodResolver(loginSchema(choices.current.via, choices.current.method))(values, context, options)

  const form = useForm<Values>({
    resolver,
    defaultValues: { email: '', country: DEFAULT_COUNTRY, phone_number: '', password: '', code: '' },
  })
  const { errors, isSubmitting } = form.formState
  const [email, country, phoneNumber] = useWatch({
    control: form.control,
    name: ['email', 'country', 'phone_number'],
  })
  const target = via === 'email' ? email.trim().toLowerCase() : toE164(country, phoneNumber)
  const codeSent = codes.sentTo === target
  const what = via === 'email' ? 'email' : 'mobile number'

  function choose(nextVia: OtpChannel, nextMethod: Method) {
    choices.current = { via: nextVia, method: nextMethod }
    setVia(nextVia)
    setMethod(nextMethod)
    setError(undefined)
    form.clearErrors()
    form.setValue('code', '')
  }

  async function sendCode() {
    setError(undefined)
    if (!(await form.trigger(via === 'email' ? 'email' : 'phone_number'))) return
    try {
      await codes.send(via, target, delivery)
      form.setValue('code', '')
      setTimeout(() => form.setFocus('code'), 50)
    } catch (e) {
      setError(errorText(e))
    }
  }

  async function onSubmit(values: Values) {
    setError(undefined)
    try {
      const tokens =
        method === 'password'
          ? await api.post<TokenResponse>('/auth/login', {
              identifier: target,
              password: values.password,
            })
          : await api.post<TokenResponse>('/auth/login/otp', {
              channel: via,
              target,
              code: values.code,
            })
      await signIn(tokens)
      navigate(from, { replace: true })
    } catch (e) {
      const message = errorText(e)
      if (method === 'code' && /code/i.test(message)) form.setError('code', { message })
      else setError(message)
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
      <FormProvider {...form}>
        <form
          noValidate
          onSubmit={(e) => {
            // In code mode, the first press sends the code.
            if (method === 'code' && !codeSent) {
              e.preventDefault()
              void sendCode()
              return
            }
            void form.handleSubmit(onSubmit)(e)
          }}
        >
          <FieldGroup>
            <SegmentedToggle
              label="Log in with"
              options={CONTACT_OPTIONS}
              value={via}
              onChange={(option) => choose(option, method)}
            />

            <FormError message={error} />

            {via === 'email' ? (
              <TextField
                label="Email"
                type="email"
                autoComplete="email"
                autoFocus
                registration={form.register('email')}
                error={errors.email}
              />
            ) : (
              <PhoneField />
            )}

            {method === 'code' && via === 'phone' && phoneChannels.length > 1 && (
              <SegmentedToggle
                label="Send the code by"
                options={DELIVERY_OPTIONS}
                value={delivery}
                onChange={(option) => {
                  setDelivery(option)
                  codes.reset()
                }}
              />
            )}

            {method === 'password' ? (
              <>
                <PasswordField
                  label="Password"
                  autoComplete="current-password"
                  registration={form.register('password')}
                  error={errors.password}
                />
                <div className="-mt-3 text-right text-sm">
                  <Link to="/forgot-password" className="text-muted-foreground hover:underline">
                    Forgot password?
                  </Link>
                </div>
              </>
            ) : (
              codeSent && (
                <Field data-invalid={!!errors.code}>
                  <div className="flex items-center justify-between">
                    <FieldLabel htmlFor="code">Login code</FieldLabel>
                    <button
                      type="button"
                      className="text-sm text-muted-foreground hover:underline disabled:no-underline disabled:opacity-60"
                      disabled={codes.sending || codes.cooldown > 0}
                      onClick={sendCode}
                    >
                      {codes.buttonLabel(target)}
                    </button>
                  </div>
                  <Controller
                    control={form.control}
                    name="code"
                    render={({ field }) => (
                      <CodeInput
                        id="code"
                        ref={field.ref}
                        value={field.value}
                        onChange={field.onChange}
                        onBlur={field.onBlur}
                        invalid={!!errors.code}
                      />
                    )}
                  />
                  {!errors.code && (
                    <FieldDescription className="flex items-start gap-1.5">
                      <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                      <span>
                        If this {what} has a Doctoo account, a code is on its way
                        {via === 'email'
                          ? ' (check spam too)'
                          : delivery === 'whatsapp'
                            ? ' on WhatsApp'
                            : ' by SMS'}
                        . It expires in{' '}
                        {codes.ttlMinutes} minutes.
                      </span>
                    </FieldDescription>
                  )}
                  <FieldError errors={[errors.code]} />
                </Field>
              )
            )}

            {method === 'code' && !codeSent ? (
              <Button type="submit" disabled={codes.sending}>
                {codes.sending
                  ? 'Sending…'
                  : via === 'email'
                    ? 'Email me a login code'
                    : delivery === 'whatsapp'
                      ? 'Send code on WhatsApp'
                      : 'Text me a login code'}
              </Button>
            ) : (
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Logging in…' : 'Log in'}
              </Button>
            )}

            <Button
              type="button"
              variant="link"
              className="-mt-2 h-auto p-0 text-muted-foreground"
              onClick={() => choose(via, method === 'password' ? 'code' : 'password')}
            >
              {method === 'password'
                ? 'Log in with a one-time code instead'
                : 'Log in with password instead'}
            </Button>
          </FieldGroup>
        </form>
      </FormProvider>
    </AuthLayout>
  )
}
