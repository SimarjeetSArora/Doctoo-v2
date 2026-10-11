/** A user-friendly message for any thrown error. */
export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
