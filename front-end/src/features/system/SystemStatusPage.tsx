import { useQuery } from '@tanstack/react-query'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { apiFetch } from '@/lib/api'

type Health = { status: string; database: 'ok' | 'unreachable' }

function StatusRow({ label, ok, pending }: { label: string; ok: boolean; pending: boolean }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm">{label}</span>
      {pending ? (
        <Badge variant="secondary">Checking…</Badge>
      ) : (
        <Badge variant={ok ? 'default' : 'destructive'}>{ok ? 'Connected' : 'Unreachable'}</Badge>
      )}
    </div>
  )
}

export function SystemStatusPage() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<Health>('/health'),
    retry: false,
  })

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Doctoo</CardTitle>
          <CardDescription>Clinic management — system status</CardDescription>
        </CardHeader>
        <CardContent className="divide-y">
          <StatusRow label="Backend API" ok={health.isSuccess} pending={health.isPending} />
          <StatusRow
            label="Database"
            ok={health.data?.database === 'ok'}
            pending={health.isPending}
          />
        </CardContent>
      </Card>
    </main>
  )
}
