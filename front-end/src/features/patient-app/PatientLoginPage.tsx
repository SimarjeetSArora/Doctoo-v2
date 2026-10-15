import { useQuery } from '@tanstack/react-query'
import { CircleCheck, HeartPulse } from 'lucide-react'
import { useState } from 'react'
import { Controller, FormProvider, useForm, useWatch } from 'react-hook-form'
import { Link } from 'react-router'

import { CodeInput } from '@/components/CodeInput'
import { SegmentedToggle } from '@/components/SegmentedToggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { FormError } from '@/features/auth/FormError'
import { PhoneField } from '@/features/auth/ProfileFields'
import { useCodeSender } from '@/features/auth/use-code-sender'
import { api, patientApi } from '@/lib/api'
import { DELIVERY_OPTIONS } from '@/lib/contact-options'
import { DEFAULT_COUNTRY } from '@/lib/countries'
import { errorText } from '@/lib/errors'
import { toE164 } from '@/lib/phone'
import type { AuthOptions, OtpResponse, PhoneDelivery, TokenResponse } from '@/lib/types'

import { usePatientAuth } from './patient-auth'

type Values = { country: string; phone_number: string; code: string }

export function PatientLoginPage() {
  const { signIn } = usePatientAuth()
  const [error, setError] = useState<string>()
  const options = useQuery({
    queryKey: ['auth-options'],
    queryFn: () => api.get<AuthOptions>('/auth/options'),
    staleTime: Infinity,
  })
  const channels = options.data?.phone_code_channels ?? ['whatsapp']
  const [chosen, setChosen] = useState<PhoneDelivery>('whatsapp')
  const delivery = channels.includes(chosen) ? chosen : channels[0]

  const codes = useCodeSender((_channel, target, how) =>
    patientApi.post<OtpResponse>('/patient/auth/otp', { phone: target, delivery: how }),
  )
  const form = useForm<Values>({
    defaultValues: { country: DEFAULT_COUNTRY, phone_number: '', code: '' },
  })
  const { errors, isSubmitting } = form.formState
  const [country, phoneNumber] = useWatch({ control: form.control, name: ['country', 'phone_number'] })
  const phone = toE164(country, phoneNumber)
  const codeSent = codes.sentTo === phone

  async function sendCode() {
    setError(undefined)
    form.clearErrors()
    const digits = phoneNumber.replace(/[\s()-]/g, '')
    if (country === 'IN' ? !/^[6-9]\d{9}$/.test(digits) : !/^\d{6,14}$/.test(digits)) {
      form.setError('phone_number', { message: 'Enter the mobile number your clinic has' })
      return
    }
    try {
      await codes.send('phone', phone, delivery)
      form.setValue('code', '')
      setTimeout(() => form.setFocus('code'), 50)
    } catch (e) {
      setError(errorText(e))
    }
  }

  async function logIn(values: Values) {
    setError(undefined)
    if (!/^\d{6}$/.test(values.code)) {
      form.setError('code', { message: 'Enter the 6-digit code' })
      return
    }
    try {
      await signIn(
        await patientApi.post<TokenResponse>('/patient/auth/login', { phone, code: values.code }),
      )
    } catch (e) {
      form.setError('code', { message: errorText(e) })
    }
  }

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-4">
      <div className="flex items-center gap-2 text-lg font-semibold">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <HeartPulse className="size-4" />
        </span>
        Doctoo for patients
      </div>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">See your health records</CardTitle>
          <CardDescription>
            Your clinics, doctors, prescriptions and reports, in one place. Log in with the mobile
            number your clinic has.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FormProvider {...form}>
            <form
              noValidate
              onSubmit={(e) => {
                if (!codeSent) {
                  e.preventDefault()
                  void sendCode()
                  return
                }
                void form.handleSubmit(logIn)(e)
              }}
            >
              <FieldGroup>
                <FormError message={error} />
                <PhoneField />
                {channels.length > 1 && (
                  <SegmentedToggle
                    label="Send the code by"
                    options={DELIVERY_OPTIONS}
                    value={delivery}
                    onChange={(option) => {
                      setChosen(option)
                      codes.reset()
                    }}
                  />
                )}
                {codeSent && (
                  <Field data-invalid={!!errors.code}>
                    <div className="flex items-center justify-between">
                      <FieldLabel htmlFor="code">Code</FieldLabel>
                      <button
                        type="button"
                        className="text-sm text-muted-foreground hover:underline disabled:opacity-60"
                        disabled={codes.sending || codes.cooldown > 0}
                        onClick={sendCode}
                      >
                        {codes.buttonLabel(phone)}
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
                          invalid={!!errors.code}
                        />
                      )}
                    />
                    {!errors.code && (
                      <FieldDescription className="flex items-start gap-1.5">
                        <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
                        <span>
                          If a clinic on Doctoo has this number, a code is on its way
                          {delivery === 'whatsapp' ? ' on WhatsApp' : ' by SMS'}.
                        </span>
                      </FieldDescription>
                    )}
                    <FieldError errors={[errors.code]} />
                  </Field>
                )}
                <Button type="submit" disabled={codes.sending || isSubmitting}>
                  {!codeSent
                    ? codes.sending
                      ? 'Sending…'
                      : delivery === 'whatsapp'
                        ? 'Send code on WhatsApp'
                        : 'Text me a code'
                    : isSubmitting
                      ? 'Logging in…'
                      : 'Log in'}
                </Button>
              </FieldGroup>
            </form>
          </FormProvider>
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">
        Clinic staff?{' '}
        <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
          Log in here
        </Link>
      </p>
    </main>
  )
}
