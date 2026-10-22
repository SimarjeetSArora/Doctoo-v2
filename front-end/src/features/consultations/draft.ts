import type { PrescriptionItem, Visit, Vitals } from '@/lib/types'

/** The consultation as edited on screen (inputs hold text; converted when saving). */
export type Draft = {
  vitals: Record<keyof Vitals, string>
  complaints: string
  examination: string
  diagnosis: string
  advice: string
  follow_up_date: string
  items: ItemDraft[]
}

export type ItemDraft = Record<keyof PrescriptionItem, string> & { key: number }

export const VITAL_FIELDS: { key: keyof Vitals; label: string; unit: string; step?: string }[] = [
  { key: 'pulse', label: 'Pulse', unit: '/min' },
  { key: 'temperature_f', label: 'Temp', unit: '°F', step: '0.1' },
  { key: 'spo2', label: 'SpO₂', unit: '%' },
  { key: 'respiratory_rate', label: 'Resp. rate', unit: '/min' },
  { key: 'blood_sugar', label: 'Sugar', unit: 'mg/dL' },
  { key: 'weight_kg', label: 'Weight', unit: 'kg', step: '0.1' },
  { key: 'height_cm', label: 'Height', unit: 'cm', step: '0.1' },
]

const ALL_VITALS: (keyof Vitals)[] = [
  'bp_systolic',
  'bp_diastolic',
  'pulse',
  'temperature_f',
  'spo2',
  'respiratory_rate',
  'blood_sugar',
  'weight_kg',
  'height_cm',
]

let nextKey = 1

export function emptyItem(): ItemDraft {
  return { key: nextKey++, medicine: '', dose: '', timing: '', duration: '', instructions: '' }
}

export function toDraft(visit: Visit): Draft {
  const vitals = Object.fromEntries(
    ALL_VITALS.map((k) => [k, visit.vitals[k] == null ? '' : String(visit.vitals[k])]),
  ) as Draft['vitals']
  return {
    vitals,
    complaints: visit.complaints ?? '',
    examination: visit.examination ?? '',
    diagnosis: visit.diagnosis ?? '',
    advice: visit.advice ?? '',
    follow_up_date: visit.follow_up_date ?? '',
    items: visit.items.length
      ? visit.items.map((i) => ({
          key: nextKey++,
          medicine: i.medicine,
          dose: i.dose,
          timing: i.timing ?? '',
          duration: i.duration ?? '',
          instructions: i.instructions ?? '',
        }))
      : [emptyItem()],
  }
}

/** What the API expects. Empty medicine rows are left out. */
export function toPayload(draft: Draft) {
  const vitals = Object.fromEntries(
    Object.entries(draft.vitals)
      .filter(([, v]) => v.trim() !== '')
      .map(([k, v]) => [k, Number(v)]),
  )
  return {
    vitals,
    complaints: draft.complaints || null,
    examination: draft.examination || null,
    diagnosis: draft.diagnosis || null,
    advice: draft.advice || null,
    follow_up_date: draft.follow_up_date || null,
    items: draft.items
      .filter((i) => i.medicine.trim())
      .map((i) => ({
        medicine: i.medicine.trim(),
        dose: i.dose.trim(),
        timing: i.timing || null,
        duration: i.duration || null,
        instructions: i.instructions || null,
      })),
  }
}
