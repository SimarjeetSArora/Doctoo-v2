import { Stethoscope } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/** Centered card used by login, sign-up, password reset and invite pages. */
export function AuthLayout({
  title,
  description,
  children,
  footer,
  wide = false,
}: {
  title: string
  description?: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
  /** Wider card for longer forms (sign-up). */
  wide?: boolean
}) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-4">
      <div className="flex items-center gap-2 text-lg font-semibold">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Stethoscope className="size-4" />
        </span>
        Doctoo
      </div>
      <Card className={wide ? 'w-full max-w-lg' : 'w-full max-w-sm'}>
        <CardHeader>
          <CardTitle className="text-xl">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
      {footer && <div className="text-sm text-muted-foreground">{footer}</div>}
    </main>
  )
}
