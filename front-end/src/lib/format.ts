import { GENDER_LABELS, type Gender } from '@/lib/types'

/** 12 Oct 2026 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** "34 y · Female" — whatever is known. */
export function ageAndGender(age: number | null, gender: Gender | null): string {
  return [age !== null ? `${age} y` : null, gender ? GENDER_LABELS[gender] : null]
    .filter(Boolean)
    .join(' · ')
}

export function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean)
  return `${words[0]?.[0] ?? ''}${words.length > 1 ? words[words.length - 1][0] : ''}`.toUpperCase()
}

/** Today as yyyy-mm-dd (for date inputs' max). */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}
