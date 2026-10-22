import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { DEFAULT_ZONE } from '@/lib/time'
import type { Appointment, AppointmentStatus, Clinic, Doctor } from '@/lib/types'

/** The current clinic's time zone (appointment times are shown in clinic time). */
export function useClinicZone(): string {
  const clinic = useQuery({
    queryKey: ['clinic'],
    queryFn: () => api.get<Clinic>('/clinics/current'),
    staleTime: 5 * 60_000,
  })
  return clinic.data?.timezone ?? DEFAULT_ZONE
}

export function useDoctors() {
  return useQuery({
    queryKey: ['doctors'],
    queryFn: () => api.get<Doctor[]>('/doctors'),
    staleTime: 60_000,
  })
}

/** Check in / start / complete / cancel / no-show. */
export function useChangeStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: AppointmentStatus }) =>
      api.post<Appointment>(`/appointments/${id}/status`, { status }),
    onSuccess: (appointment) => {
      if (appointment.status === 'arrived' && appointment.token_number) {
        toast.success(`${appointment.patient_name} checked in — token #${appointment.token_number}`)
      }
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['slots'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })
}
