import { Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { emptyItem, type ItemDraft } from './draft'
import { MedicineInput } from './MedicineInput'

const DOSES = ['1-0-1', '1-0-0', '0-0-1', '1-1-1', '0-1-0', 'SOS']
const TIMINGS = ['After food', 'Before food', 'With food', 'Empty stomach', 'At bedtime']
const DURATIONS = ['3 days', '5 days', '7 days', '10 days', '2 weeks', '1 month']

function Chips({
  options,
  value,
  onPick,
  label,
}: {
  options: string[]
  value: string
  onPick: (value: string) => void
  label: string
}) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onPick(option === value ? '' : option)}
          className={cn(
            'rounded-full border px-2 py-0.5 text-xs transition-colors hover:border-primary',
            option === value && 'border-primary bg-primary text-primary-foreground',
          )}
        >
          {option}
        </button>
      ))}
    </div>
  )
}

export function PrescriptionEditor({
  items,
  onChange,
}: {
  items: ItemDraft[]
  onChange: (items: ItemDraft[]) => void
}) {
  function update(key: number, change: Partial<ItemDraft>) {
    onChange(items.map((item) => (item.key === key ? { ...item, ...change } : item)))
  }

  return (
    <div className="flex flex-col gap-3">
      {items.map((item, index) => (
        <div key={item.key} className="flex flex-col gap-3 rounded-lg border p-3">
          <div className="flex items-start gap-2">
            <span className="w-6 pt-2 text-right text-sm text-muted-foreground tabular-nums">
              {index + 1}.
            </span>
            <div className="flex-1">
              <label htmlFor={`medicine-${item.key}`} className="sr-only">
                Medicine {index + 1}
              </label>
              <MedicineInput
                id={`medicine-${item.key}`}
                value={item.medicine}
                autoFocus={index > 0 && !item.medicine}
                onChange={(medicine) => update(item.key, { medicine })}
              />
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove medicine ${index + 1}`}
              onClick={() =>
                onChange(items.length === 1 ? [emptyItem()] : items.filter((i) => i.key !== item.key))
              }
            >
              <Trash2 />
            </Button>
          </div>
          <div className="grid gap-3 pl-8 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Input
                aria-label={`Dose for medicine ${index + 1}`}
                placeholder="Dose (e.g. 1-0-1)"
                value={item.dose}
                onChange={(e) => update(item.key, { dose: e.target.value })}
              />
              <Chips label="Common doses" options={DOSES} value={item.dose} onPick={(dose) => update(item.key, { dose })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Input
                aria-label={`When to take medicine ${index + 1}`}
                placeholder="When"
                value={item.timing}
                onChange={(e) => update(item.key, { timing: e.target.value })}
              />
              <Chips label="When" options={TIMINGS} value={item.timing} onPick={(timing) => update(item.key, { timing })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Input
                aria-label={`Duration for medicine ${index + 1}`}
                placeholder="Duration"
                value={item.duration}
                onChange={(e) => update(item.key, { duration: e.target.value })}
              />
              <Chips
                label="Duration"
                options={DURATIONS}
                value={item.duration}
                onPick={(duration) => update(item.key, { duration })}
              />
            </div>
          </div>
          <div className="pl-8">
            <Input
              aria-label={`Instructions for medicine ${index + 1}`}
              placeholder="Instructions (optional), e.g. Complete the course"
              value={item.instructions}
              onChange={(e) => update(item.key, { instructions: e.target.value })}
            />
          </div>
        </div>
      ))}
      <Button type="button" variant="outline" className="w-fit" onClick={() => onChange([...items, emptyItem()])}>
        <Plus /> Add medicine
      </Button>
    </div>
  )
}
