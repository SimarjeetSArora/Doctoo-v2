import { z } from 'zod'

import { DEFAULT_COUNTRY } from '@/lib/countries'
import { toE164 } from '@/lib/phone'
import type { Salutation } from '@/lib/types'

export const SALUTATIONS = ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Miss', 'Prof.'] as const satisfies readonly Salutation[]

const noDigits = /^[^0-9]*$/
const personName = z
  .string()
  .trim()
  .min(1, 'Required')
  .max(100, 'Too long')
  .regex(noDigits, "Names can't contain numbers")

/** Name + phone fields shared by sign-up and invitation acceptance. */
export const profileFields = {
  salutation: z.enum(SALUTATIONS, { message: 'Choose a title' }),
  first_name: personName,
  middle_name: z.string().trim().max(100, 'Too long').regex(noDigits, "Names can't contain numbers"),
  last_name: personName,
  country: z.string(),
  phone_number: z.string().trim().min(1, 'Required'),
}

export type ProfileFormValues = {
  salutation: (typeof SALUTATIONS)[number]
  first_name: string
  middle_name: string
  last_name: string
  country: string
  phone_number: string
}

export const profileDefaults: Partial<ProfileFormValues> = {
  middle_name: '',
  country: DEFAULT_COUNTRY,
  phone_number: '',
}

/** Quick in-browser phone check (the server does the full check per country). */
export function checkPhone(values: { country: string; phone_number: string }, ctx: z.RefinementCtx) {
  const digits = values.phone_number.replace(/[\s()-]/g, '')
  const ok =
    values.country === 'IN' ? /^[6-9]\d{9}$/.test(digits) : /^\d{6,14}$/.test(digits)
  if (!ok) {
    ctx.addIssue({
      code: 'custom',
      path: ['phone_number'],
      message:
        values.country === 'IN'
          ? 'Enter a 10-digit mobile number starting with 6, 7, 8 or 9'
          : 'Enter a valid mobile number',
    })
  }
}

/** Converts form values to the API's profile shape. */
export function toProfile(values: ProfileFormValues) {
  return {
    salutation: values.salutation,
    first_name: values.first_name,
    middle_name: values.middle_name || null,
    last_name: values.last_name,
    phone: toE164(values.country, values.phone_number),
  }
}
