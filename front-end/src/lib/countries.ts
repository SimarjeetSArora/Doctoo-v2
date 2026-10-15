// Country dialling codes offered in phone fields. The backend does the authoritative validation.
export type Country = { iso: string; name: string; dial: string }

export const COUNTRIES: Country[] = [
  { iso: 'IN', name: 'India', dial: '+91' },
  { iso: 'AE', name: 'United Arab Emirates', dial: '+971' },
  { iso: 'AU', name: 'Australia', dial: '+61' },
  { iso: 'BD', name: 'Bangladesh', dial: '+880' },
  { iso: 'BH', name: 'Bahrain', dial: '+973' },
  { iso: 'CA', name: 'Canada', dial: '+1' },
  { iso: 'DE', name: 'Germany', dial: '+49' },
  { iso: 'FR', name: 'France', dial: '+33' },
  { iso: 'GB', name: 'United Kingdom', dial: '+44' },
  { iso: 'KW', name: 'Kuwait', dial: '+965' },
  { iso: 'LK', name: 'Sri Lanka', dial: '+94' },
  { iso: 'MY', name: 'Malaysia', dial: '+60' },
  { iso: 'NP', name: 'Nepal', dial: '+977' },
  { iso: 'NZ', name: 'New Zealand', dial: '+64' },
  { iso: 'OM', name: 'Oman', dial: '+968' },
  { iso: 'QA', name: 'Qatar', dial: '+974' },
  { iso: 'SA', name: 'Saudi Arabia', dial: '+966' },
  { iso: 'SG', name: 'Singapore', dial: '+65' },
  { iso: 'US', name: 'United States', dial: '+1' },
]

export const DEFAULT_COUNTRY = 'IN'

export function dialCode(iso: string): string {
  return COUNTRIES.find((c) => c.iso === iso)?.dial ?? '+91'
}
