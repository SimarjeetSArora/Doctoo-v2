import { CircleAlert } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'

/** Error banner for a whole form (e.g. "Incorrect email or password"). */
export function FormError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
