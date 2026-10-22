import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { ageAndGender } from '@/lib/format'
import { formatPhone } from '@/lib/phone'
import type { Patient, PatientPage } from '@/lib/types'

export type PickedPatient = Pick<Patient, 'id' | 'full_name' | 'phone'>

/** Search-as-you-type patient chooser (name or mobile number). */
export function PatientPicker({
  value,
  onChange,
  invalid,
}: {
  value: PickedPatient | null
  onChange: (patient: PickedPatient | null) => void
  invalid?: boolean
}) {
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(timer)
  }, [query])

  const results = useQuery({
    queryKey: ['patients', 'picker', debounced],
    queryFn: () => api.get<PatientPage>(`/patients?q=${encodeURIComponent(debounced)}&limit=6`),
    enabled: !value && debounced.length >= 2,
  })

  if (value) {
    return (
      <div className="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2">
        <div>
          <div className="text-sm font-medium">{value.full_name}</div>
          <div className="text-xs text-muted-foreground">{formatPhone(value.phone)}</div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Choose a different patient"
          onClick={() => {
            onChange(null)
            setQuery('')
          }}
        >
          <X />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id="patient"
          className="pl-9"
          placeholder="Search name or mobile number"
          aria-invalid={invalid}
          autoComplete="off"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {debounced.length >= 2 && (
        <ul className="max-h-56 overflow-y-auto rounded-md border" aria-label="Matching patients">
          {results.data?.items.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                onClick={() => onChange({ id: p.id, full_name: p.full_name, phone: p.phone })}
              >
                <span>
                  <span className="font-medium">{p.full_name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {ageAndGender(p.age, p.gender)}
                  </span>
                </span>
                <span className="text-xs text-muted-foreground">{formatPhone(p.phone)}</span>
              </button>
            </li>
          ))}
          {results.data?.items.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No patients found. Register them first from Patients.
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
