import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search, UserPlus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api } from '@/lib/api'
import { ageAndGender, formatDate } from '@/lib/format'
import { formatPhone } from '@/lib/phone'
import type { PatientPage } from '@/lib/types'

const PAGE_SIZE = 20

/** The value, but only after it stops changing for `ms` (so we don't search on every key). */
function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

export function PatientsPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const q = useDebounced(query.trim())

  const patients = useQuery({
    queryKey: ['patients', q, page],
    queryFn: () =>
      api.get<PatientPage>(
        `/patients?q=${encodeURIComponent(q)}&limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
      ),
    placeholderData: keepPreviousData,
  })
  const total = patients.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Patients</h1>
          <p className="text-muted-foreground">
            {patients.isPending ? 'Loading…' : `${total} patient${total === 1 ? '' : 's'}`}
          </p>
        </div>
        <Button asChild>
          <Link to="/patients/new">
            <UserPlus />
            Register patient
          </Link>
        </Button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          autoFocus
          placeholder="Search by name or mobile number"
          aria-label="Search patients"
          className="pl-9"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setPage(0)
          }}
        />
      </div>

      <Card>
        <CardContent className="overflow-x-auto px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Name</TableHead>
                <TableHead>Mobile</TableHead>
                <TableHead>Blood group</TableHead>
                <TableHead className="pr-6">Registered</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {patients.data?.items.map((p) => (
                <TableRow
                  key={p.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/patients/${p.id}`)}
                >
                  <TableCell className="pl-6">
                    <Link
                      to={`/patients/${p.id}`}
                      className="font-medium hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {p.full_name}
                    </Link>
                    <div className="text-sm text-muted-foreground">{ageAndGender(p.age, p.gender)}</div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{formatPhone(p.phone)}</TableCell>
                  <TableCell>
                    {p.blood_group ? <Badge variant="outline">{p.blood_group}</Badge> : '—'}
                  </TableCell>
                  <TableCell className="pr-6 whitespace-nowrap text-muted-foreground">
                    {formatDate(p.created_at)}
                  </TableCell>
                </TableRow>
              ))}
              {patients.data && patients.data.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                    {q ? (
                      <>No patients match “{q}”.</>
                    ) : (
                      <>
                        No patients yet.{' '}
                        <Link to="/patients/new" className="text-foreground underline">
                          Register the first one
                        </Link>
                        .
                      </>
                    )}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-3 text-sm">
          <span className="text-muted-foreground">
            Page {page + 1} of {pages}
          </span>
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
