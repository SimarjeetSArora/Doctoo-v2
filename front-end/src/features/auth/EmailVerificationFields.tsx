import { CircleCheck, Mail } from 'lucide-react'
import { Controller, useFormContext, useWatch } from 'react-hook-form'

import { CodeInput } from '@/components/CodeInput'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { errorText } from '@/lib/errors'

import type { useCodeSender } from './use-code-sender'

type Fields = { email: string; email_code: string }

/**
 * Email input with a "Send code" button, then six boxes for the emailed code.
 * Must be inside a react-hook-form <FormProvider> with `email` and `email_code` fields.
 */
export function EmailVerificationFields({
  sender,
}: {
  sender: ReturnType<typeof useCodeSender>
}) {
  const { control, register, formState, trigger, setValue, setError, clearErrors, setFocus } =
    useFormContext<Fields>()
  const { errors } = formState
  const email = (useWatch({ control, name: 'email' }) ?? '').trim().toLowerCase()
  const codeSent = sender.sentTo === email // editing the email hides the code boxes

  async function sendCode() {
    if (!(await trigger('email'))) return
    try {
      await sender.send('email', email)
      setValue('email_code', '')
      clearErrors(['email', 'email_code'])
      setTimeout(() => setFocus('email_code'), 50)
    } catch (e) {
      setError('email', { message: errorText(e) })
    }
  }

  return (
    <>
      <Field data-invalid={!!errors.email}>
        <FieldLabel htmlFor="email">Email</FieldLabel>
        <div className="flex gap-2">
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            {...register('email')}
          />
          <Button
            type="button"
            variant="outline"
            className="w-32 shrink-0"
            disabled={sender.sending || (codeSent && sender.cooldown > 0)}
            onClick={sendCode}
          >
            {sender.buttonLabel(email)}
          </Button>
        </div>
        {!codeSent && !errors.email && (
          <FieldDescription>We&apos;ll email you a 6-digit code to confirm it&apos;s yours.</FieldDescription>
        )}
        <FieldError errors={[errors.email]} />
      </Field>

      {codeSent && (
        <Field data-invalid={!!errors.email_code}>
          <FieldLabel htmlFor="email_code" className="flex items-center gap-1.5">
            <Mail className="size-4" /> Verification code
          </FieldLabel>
          <Controller
            control={control}
            name="email_code"
            render={({ field }) => (
              <CodeInput
                id="email_code"
                ref={field.ref}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
                invalid={!!errors.email_code}
              />
            )}
          />
          {!errors.email_code && (
            <FieldDescription className="flex items-start gap-1.5">
              <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />
              <span>
                Code sent to <strong>{sender.sentTo}</strong>. It expires in {sender.ttlMinutes}{' '}
                minutes; check your spam folder if you can&apos;t find it.
              </span>
            </FieldDescription>
          )}
          <FieldError errors={[errors.email_code]} />
        </Field>
      )}
    </>
  )
}
