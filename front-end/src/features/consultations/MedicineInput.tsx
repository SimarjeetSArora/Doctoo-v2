import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'

type Suggestion = { name: string; times_used: number }

/** Medicine name with suggestions from what this clinic has prescribed before. */
export function MedicineInput({
  value,
  onChange,
  id,
  autoFocus,
}: {
  value: string
  onChange: (value: string) => void
  id: string
  autoFocus?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setQuery(value.trim()), 200)
    return () => clearTimeout(timer)
  }, [value])

  const suggestions = useQuery({
    queryKey: ['medicines', query],
    queryFn: () => api.get<Suggestion[]>(`/medicines?q=${encodeURIComponent(query)}`),
    enabled: open && query.length >= 2,
    staleTime: 60_000,
  })
  const items = (suggestions.data ?? []).filter((s) => s.name.toLowerCase() !== value.trim().toLowerCase())

  return (
    <div className="relative">
      <Input
        id={id}
        value={value}
        autoFocus={autoFocus}
        autoComplete="off"
        placeholder="e.g. Paracetamol 650 mg"
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && items.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border bg-popover shadow-md">
          {items.map((s) => (
            <li key={s.name}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-muted"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onChange(s.name)
                  setOpen(false)
                }}
              >
                {s.name}
                <span className="text-xs text-muted-foreground">used {s.times_used}×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
