import type { UseFormRegisterReturn } from 'react-hook-form'

import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

type TextFieldProps = {
  label: string
  registration: UseFormRegisterReturn
  error?: { message?: string }
  description?: string
} & Omit<React.ComponentProps<typeof Input>, 'name'>

/** Label + input + validation message, wired to react-hook-form's register(). */
export function TextField({ label, registration, error, description, ...inputProps }: TextFieldProps) {
  const id = inputProps.id ?? registration.name
  return (
    <Field data-invalid={!!error}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input id={id} aria-invalid={!!error} {...inputProps} {...registration} />
      {description && !error && <FieldDescription>{description}</FieldDescription>}
      <FieldError errors={[error]} />
    </Field>
  )
}
