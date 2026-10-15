import { dialCode } from '@/lib/countries'

/** Builds an international number (+919876543210) from a country and what the user typed. */
export function toE164(countryIso: string, nationalNumber: string): string {
  return `${dialCode(countryIso)}${nationalNumber.replace(/[\s()-]/g, '')}`
}

/** Friendlier display for stored numbers: +919876543210 → +91 98765 43210. */
export function formatPhone(e164: string | null | undefined): string {
  if (!e164) return ''
  const india = /^\+91(\d{5})(\d{5})$/.exec(e164)
  return india ? `+91 ${india[1]} ${india[2]}` : e164
}
