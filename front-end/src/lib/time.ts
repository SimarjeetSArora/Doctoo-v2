// Dates and times in the clinic's time zone (not the browser's), so everyone sees clinic time.

export const DEFAULT_ZONE = 'Asia/Kolkata'

/** "2026-10-20" for an instant, in the given zone. */
export function dateInZone(instant: Date | string, zone: string): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: zone }).format(new Date(instant))
}

export function todayInZone(zone: string): string {
  return dateInZone(new Date(), zone)
}

/** "2026-10-20" + n days (calendar arithmetic on the date only). */
export function addDays(day: string, days: number): string {
  const [y, m, d] = day.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d + days))
  return date.toISOString().slice(0, 10)
}

/** 0 = Monday … 6 = Sunday, like the backend. */
export function weekdayOf(day: string): number {
  const [y, m, d] = day.split('-').map(Number)
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7
}

export function startOfWeek(day: string): string {
  return addDays(day, -weekdayOf(day))
}

/** "10:30 am" */
export function formatTime(instant: string, zone: string): string {
  return new Intl.DateTimeFormat('en-IN', { timeZone: zone, hour: 'numeric', minute: '2-digit' })
    .format(new Date(instant))
}

/** "Mon, 20 Oct" (date-only strings are shown as that calendar day). */
export function formatDay(day: string, options: Intl.DateTimeFormatOptions = {}): string {
  const [y, m, d] = day.split('-').map(Number)
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    ...options,
  }).format(new Date(Date.UTC(y, m - 1, d)))
}

/** Interprets "2026-10-20" + "10:30" in the zone and returns an ISO instant with offset. */
export function zonedIso(day: string, hhmm: string, zone: string): string {
  // Find the zone's offset at that wall-clock time (correct for fixed-offset zones like IST and
  // close enough around DST changes for clinic hours).
  const guess = new Date(`${day}T${hhmm}:00Z`)
  const asZone = new Date(guess.toLocaleString('en-US', { timeZone: zone }))
  const asUtc = new Date(guess.toLocaleString('en-US', { timeZone: 'UTC' }))
  return new Date(guess.getTime() - (asZone.getTime() - asUtc.getTime())).toISOString()
}

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

/** "10:00:00" → "10:00 am" */
export function formatClock(hhmmss: string): string {
  const [h, m] = hhmmss.split(':').map(Number)
  const suffix = h < 12 ? 'am' : 'pm'
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${suffix}`
}
