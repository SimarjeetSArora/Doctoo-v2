import { Badge } from '@/components/ui/badge'
import { STATUS_LABELS, type AppointmentStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

const STYLES: Record<AppointmentStatus, string> = {
  booked: 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200',
  arrived:
    'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200',
  in_consultation:
    'border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-200',
  completed:
    'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200',
  no_show: 'text-muted-foreground',
  cancelled: 'text-muted-foreground line-through',
}

export function StatusBadge({ status }: { status: AppointmentStatus }) {
  return (
    <Badge variant="outline" className={cn(STYLES[status])}>
      {STATUS_LABELS[status]}
    </Badge>
  )
}
