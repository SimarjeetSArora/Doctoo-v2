import { REGEXP_ONLY_DIGITS } from 'input-otp'

import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp'

/** Six boxes for a one-time code. */
export function CodeInput({
  id,
  value,
  onChange,
  onBlur,
  invalid,
  ref,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  invalid?: boolean
  ref?: React.Ref<HTMLInputElement>
}) {
  return (
    <InputOTP
      id={id}
      ref={ref}
      maxLength={6}
      pattern={REGEXP_ONLY_DIGITS}
      inputMode="numeric"
      autoComplete="one-time-code"
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      aria-invalid={invalid}
    >
      <InputOTPGroup>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <InputOTPSlot key={i} index={i} aria-invalid={invalid} />
        ))}
      </InputOTPGroup>
    </InputOTP>
  )
}
