import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MailPlus, MoreHorizontal } from 'lucide-react'
import { useRef, useState } from 'react'
import { Controller, FormProvider, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { SegmentedToggle } from '@/components/SegmentedToggle'
import { TextField } from '@/components/TextField'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAuth } from '@/features/auth/auth-context'
import { FormError } from '@/features/auth/FormError'
import { errorText } from '@/lib/errors'
import { formatPhone, toE164 } from '@/lib/phone'
import { checkPhone } from '@/features/auth/profile'
import { PhoneField } from '@/features/auth/ProfileFields'
import { emailField } from '@/features/auth/schemas'
import { api } from '@/lib/api'
import { CONTACT_OPTIONS } from '@/lib/contact-options'
import { DEFAULT_COUNTRY } from '@/lib/countries'
import { type Invitation, type Member, type OtpChannel, type Role, ROLE_LABELS } from '@/lib/types'

const ROLES = Object.keys(ROLE_LABELS) as Role[]

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function TeamPage() {
  const { me, membership } = useAuth()
  const isOwner = membership?.role === 'owner'
  const queryClient = useQueryClient()

  const members = useQuery({
    queryKey: ['members'],
    queryFn: () => api.get<Member[]>('/clinics/current/members'),
  })
  const invitations = useQuery({
    queryKey: ['invitations'],
    queryFn: () => api.get<Invitation[]>('/invitations'),
    enabled: isOwner,
  })

  const updateMember = useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean }) =>
      api.patch<Member>(`/clinics/current/members/${id}`, body),
    onSuccess: () => {
      toast.success('Team member updated')
      queryClient.invalidateQueries({ queryKey: ['members'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  const revokeInvitation = useMutation({
    mutationFn: (id: string) => api.delete(`/invitations/${id}`),
    onSuccess: () => {
      toast.success('Invitation cancelled')
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
    },
    onError: (e) => toast.error(errorText(e)),
  })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Team</h1>
          <p className="text-muted-foreground">Everyone who can access {membership?.clinic_name}.</p>
        </div>
        {isOwner && <InviteDialog />}
      </div>

      <Card>
        <CardContent className="overflow-x-auto px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Joined</TableHead>
                {isOwner && <TableHead className="w-12 pr-6" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.isPending && (
                <TableRow>
                  <TableCell colSpan={5} className="pl-6 text-muted-foreground">
                    Loading…
                  </TableCell>
                </TableRow>
              )}
              {members.data?.map((m) => (
                <TableRow key={m.id} className={m.is_active ? undefined : 'opacity-60'}>
                  <TableCell className="pl-6">
                    <div className="font-medium">
                      {m.full_name}
                      {m.user_id === me?.user.id && (
                        <span className="text-muted-foreground"> (you)</span>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {m.email}
                      {m.phone && <span className="block">{formatPhone(m.phone)}</span>}
                    </div>
                  </TableCell>
                  <TableCell>{ROLE_LABELS[m.role]}</TableCell>
                  <TableCell>
                    <Badge variant={m.is_active ? 'secondary' : 'outline'}>
                      {m.is_active ? 'Active' : 'Deactivated'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(m.joined_at)}</TableCell>
                  {isOwner && (
                    <TableCell className="pr-6">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label={`Actions for ${m.full_name}`}>
                            <MoreHorizontal />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Change role</DropdownMenuLabel>
                          {ROLES.filter((r) => r !== m.role).map((role) => (
                            <DropdownMenuItem
                              key={role}
                              onSelect={() => updateMember.mutate({ id: m.id, role })}
                            >
                              Make {ROLE_LABELS[role]}
                            </DropdownMenuItem>
                          ))}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant={m.is_active ? 'destructive' : 'default'}
                            onSelect={() => updateMember.mutate({ id: m.id, is_active: !m.is_active })}
                          >
                            {m.is_active ? 'Deactivate access' : 'Reactivate access'}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {isOwner && !!invitations.data?.length && (
        <Card>
          <CardHeader>
            <CardTitle>Pending invitations</CardTitle>
            <CardDescription>Waiting for these people to accept.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col divide-y">
            {invitations.data.map((inv) => (
              <div key={inv.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <div className="font-medium">{inv.email ?? formatPhone(inv.phone)}</div>
                  <div className="text-sm text-muted-foreground">
                    {ROLE_LABELS[inv.role]} · by {inv.email ? 'email' : 'WhatsApp'} · expires {formatDate(inv.expires_at)}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={revokeInvitation.isPending}
                  onClick={() => revokeInvitation.mutate(inv.id)}
                >
                  Cancel invite
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

type InviteValues = {
  email: string
  country: string
  phone_number: string
  role: Role
}

function inviteSchema(via: OtpChannel) {
  return z
    .object({
      email: via === 'email' ? emailField : z.string(),
      country: z.string(),
      phone_number: z.string(),
      role: z.enum(['owner', 'doctor', 'receptionist']),
    })
    .superRefine((values, ctx) => {
      if (via === 'phone') checkPhone(values, ctx)
    })
}

function InviteDialog() {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string>()
  const [via, setVia] = useState<OtpChannel>('email')
  const queryClient = useQueryClient()
  // The resolver reads the current choice, so validation follows the Email / Mobile switch.
  const viaRef = useRef(via)
  const form = useForm<InviteValues>({
    resolver: (values, context, options) =>
      zodResolver(inviteSchema(viaRef.current))(values, context, options),
    defaultValues: { email: '', country: DEFAULT_COUNTRY, phone_number: '', role: 'doctor' },
  })
  const { errors, isSubmitting } = form.formState

  async function onSubmit(values: InviteValues) {
    setError(undefined)
    const contact =
      via === 'email'
        ? { email: values.email }
        : { phone: toE164(values.country, values.phone_number) }
    try {
      await api.post<Invitation>('/invitations', { ...contact, role: values.role })
      toast.success(`Invitation sent to ${contact.email ?? formatPhone(contact.phone)}`)
      queryClient.invalidateQueries({ queryKey: ['invitations'] })
      form.reset()
      setOpen(false)
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setError(undefined)
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <MailPlus />
          Invite member
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <FormProvider {...form}>
          <form noValidate onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Invite a team member</DialogTitle>
              <DialogDescription>
                {via === 'email'
                  ? "They'll get an email with a link to join."
                  : "They'll get a WhatsApp message with a link to join."}{' '}
                The link is valid for 7 days.
              </DialogDescription>
            </DialogHeader>
            <FieldGroup className="py-6">
              <SegmentedToggle
                label="Send invitation by"
                options={CONTACT_OPTIONS}
                value={via}
                onChange={(option) => {
                  viaRef.current = option
                  setVia(option)
                  form.clearErrors()
                  setError(undefined)
                }}
              />
              <FormError message={error} />
              {via === 'email' ? (
                <TextField
                  label="Email"
                  type="email"
                  autoFocus
                  registration={form.register('email')}
                  error={errors.email}
                />
              ) : (
                <PhoneField />
              )}
              <Field>
                <FieldLabel htmlFor="role">Role</FieldLabel>
                <Controller
                  control={form.control}
                  name="role"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="role" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLES.map((role) => (
                          <SelectItem key={role} value={role}>
                            {ROLE_LABELS[role]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </Field>
            </FieldGroup>
            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Sending…' : 'Send invitation'}
              </Button>
            </DialogFooter>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  )
}
