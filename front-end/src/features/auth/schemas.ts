import { z } from 'zod'

// Same rules as the backend (app/schemas/common.py), checked in the browser first.
export const emailField = z.email('Enter a valid email address')
export const passwordField = z
  .string()
  .min(8, 'Use at least 8 characters')
  .max(128, 'Use at most 128 characters')
export const nameField = z.string().trim().min(2, 'Enter at least 2 characters').max(200)
