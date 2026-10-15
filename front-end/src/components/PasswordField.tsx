import { Check, Eye, EyeOff, X } from 'lucide-react'
import { useState } from 'react'
import type { UseFormRegisterReturn } from 'react-hook-form'

import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { passwordStrength } from '@/lib/password'
import { cn } from '@/lib/utils'

type PasswordFieldProps = {
  label: string
  registration: UseFormRegisterReturn
  error?: { message?: string }
  description?: string
  /** Pass the current value to show the strength meter under the field. */
  strengthOf?: string
} & Omit<React.ComponentProps<typeof Input>, 'name' | 'type'>

/** Password input with a show/hide toggle and an optional strength meter. */
export function PasswordField({
  label,
  registration,
  error,
  description,
  strengthOf,
  ...inputProps
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)
  const id = inputProps.id ?? registration.name
  return (
    <Field data-invalid={!!error}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <div className="relative">
        <Input
          id={id}
          type={visible ? 'text' : 'password'}
          aria-invalid={!!error}
          className="pr-10"
          {...inputProps}
          {...registration}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {strengthOf !== undefined && <StrengthMeter password={strengthOf} />}
      {description && !error && <FieldDescription>{description}</FieldDescription>}
      <FieldError errors={[error]} />
    </Field>
  )
}

const BAR_COLORS = ['bg-red-500', 'bg-orange-500', 'bg-amber-500', 'bg-emerald-600']
const LABEL_COLORS = [
  'text-muted-foreground',
  'text-red-600 dark:text-red-400',
  'text-orange-600 dark:text-orange-400',
  'text-amber-600 dark:text-amber-400',
  'text-emerald-700 dark:text-emerald-400',
]

function StrengthMeter({ password }: { password: string }) {
  if (!password) return null
  const { score, label, checks } = passwordStrength(password)
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <div className="flex items-center gap-3">
        <div className="grid flex-1 grid-cols-4 gap-1" aria-hidden>
          {[1, 2, 3, 4].map((step) => (
            <span
              key={step}
              className={cn(
                'h-1.5 rounded-full bg-muted',
                score >= step && BAR_COLORS[score - 1],
              )}
            />
          ))}
        </div>
        <span className={cn('w-16 text-right text-xs font-medium', LABEL_COLORS[score])}>
          {label}
        </span>
      </div>
      <ul className="grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
        {checks.map((check) => (
          <li
            key={check.label}
            className={cn(
              'flex items-center gap-1.5',
              check.met ? 'text-foreground' : 'text-muted-foreground',
            )}
          >
            {check.met ? (
              <Check className="size-3.5 text-emerald-600" aria-label="done" />
            ) : (
              <X className="size-3.5" aria-label="not yet" />
            )}
            {check.label}
          </li>
        ))}
      </ul>
    </div>
  )
}
