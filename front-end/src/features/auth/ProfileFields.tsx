import { Controller, useFormContext } from 'react-hook-form'

import { TextField } from '@/components/TextField'
import { Field, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { COUNTRIES } from '@/lib/countries'

import { type ProfileFormValues, SALUTATIONS } from './profile'

/** Title + first / middle / last name. Must be inside a react-hook-form <FormProvider>. */
export function NameFields({ autoFocus }: { autoFocus?: boolean }) {
  const { control, register, formState } = useFormContext<ProfileFormValues>()
  const { errors } = formState
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-[6.5rem_1fr] gap-3">
        <Field data-invalid={!!errors.salutation}>
          <FieldLabel htmlFor="salutation">Title</FieldLabel>
          <Controller
            control={control}
            name="salutation"
            render={({ field }) => (
              <Select value={field.value ?? ''} onValueChange={field.onChange}>
                <SelectTrigger
                  id="salutation"
                  className="w-full"
                  aria-invalid={!!errors.salutation}
                  onBlur={field.onBlur}
                >
                  <SelectValue placeholder="Select" />
                </SelectTrigger>
                <SelectContent>
                  {SALUTATIONS.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          <FieldError errors={[errors.salutation]} />
        </Field>
        <TextField
          label="First name"
          autoComplete="given-name"
          autoFocus={autoFocus}
          registration={register('first_name')}
          error={errors.first_name}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Middle name (optional)"
          autoComplete="additional-name"
          registration={register('middle_name')}
          error={errors.middle_name}
        />
        <TextField
          label="Last name"
          autoComplete="family-name"
          registration={register('last_name')}
          error={errors.last_name}
        />
      </div>
    </div>
  )
}

/** Country code + mobile number. Must be inside a react-hook-form <FormProvider>. */
export function PhoneField() {
  const { control, register, formState } = useFormContext<ProfileFormValues>()
  const error = formState.errors.phone_number
  return (
    <Field data-invalid={!!error}>
      <FieldLabel htmlFor="phone_number">Mobile number</FieldLabel>
      <div className="flex gap-2">
        <Controller
          control={control}
          name="country"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger className="w-28 shrink-0" aria-label="Country code">
                <SelectValue>
                  {field.value} {COUNTRIES.find((c) => c.iso === field.value)?.dial}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {COUNTRIES.map((c) => (
                  <SelectItem key={c.iso} value={c.iso}>
                    {c.name} ({c.dial})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        <Input
          id="phone_number"
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          placeholder="98765 43210"
          aria-invalid={!!error}
          {...register('phone_number')}
        />
      </div>
      <FieldError errors={[error]} />
    </Field>
  )
}
