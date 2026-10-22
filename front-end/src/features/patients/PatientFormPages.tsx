import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { Card, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import type { Patient } from '@/lib/types'

import { PatientForm } from './PatientForm'

export function NewPatientPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Register patient</h1>
      <Card>
        <CardContent>
          <PatientForm
            submitLabel="Register patient"
            onCancel={() => navigate('/patients')}
            onSubmit={async (payload) => {
              const patient = await api.post<Patient>('/patients', payload)
              queryClient.invalidateQueries({ queryKey: ['patients'] })
              toast.success(`${patient.full_name} registered`)
              navigate(`/patients/${patient.id}`, { replace: true })
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}

export function EditPatientPage() {
  const { patientId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const patient = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => api.get<Patient>(`/patients/${patientId}`),
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Edit patient</h1>
      <Card>
        <CardContent>
          {patient.isError && <p className="text-muted-foreground">Patient not found.</p>}
          {patient.data && (
            <PatientForm
              patient={patient.data}
              submitLabel="Save changes"
              onCancel={() => navigate(`/patients/${patientId}`)}
              onSubmit={async (payload) => {
                const updated = await api.patch<Patient>(`/patients/${patientId}`, payload)
                queryClient.setQueryData(['patient', patientId], updated)
                queryClient.invalidateQueries({ queryKey: ['patients'] })
                toast.success('Patient details saved')
                navigate(`/patients/${patientId}`, { replace: true })
              }}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
