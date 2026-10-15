export type StrengthCheck = { label: string; met: boolean }

export type PasswordStrength = {
  score: 0 | 1 | 2 | 3 | 4
  label: 'Too short' | 'Weak' | 'Fair' | 'Good' | 'Strong'
  checks: StrengthCheck[]
}

/** Rates a password for the strength meter (guidance only; the backend requires 8+ characters). */
export function passwordStrength(password: string): PasswordStrength {
  const checks: StrengthCheck[] = [
    { label: 'At least 8 characters', met: password.length >= 8 },
    { label: 'Upper and lower case letters', met: /[a-z]/.test(password) && /[A-Z]/.test(password) },
    { label: 'A number', met: /\d/.test(password) },
    { label: 'A symbol (e.g. ! @ # $)', met: /[^A-Za-z0-9]/.test(password) },
  ]
  if (password.length < 8) return { score: 0, label: 'Too short', checks }

  let met = checks.filter((c) => c.met).length // 1–4 (length is always met here)
  if (password.length >= 12 && met >= 3) met = 4
  const score = Math.max(1, met) as 1 | 2 | 3 | 4
  const labels = { 1: 'Weak', 2: 'Fair', 3: 'Good', 4: 'Strong' } as const
  return { score, label: labels[score], checks }
}
