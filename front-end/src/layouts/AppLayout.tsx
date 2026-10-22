import {
  CalendarDays,
  Check,
  ChevronsUpDown,
  Clock,
  LayoutDashboard,
  LogOut,
  MonitorSmartphone,
  Settings,
  Stethoscope,
  Users,
  UsersRound,
} from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { useAuth } from '@/features/auth/auth-context'
import { ROLE_LABELS } from '@/lib/types'

type NavItem = { label: string; to: string; icon: React.ElementType; soon?: boolean }

const CLINIC_NAV: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { label: 'Patients', to: '/patients', icon: UsersRound },
  { label: 'Appointments', to: '/appointments', icon: CalendarDays },
]
const ADMIN_NAV: NavItem[] = [
  { label: 'Doctor hours', to: '/doctor-hours', icon: Clock },
  { label: 'Team', to: '/team', icon: Users },
  { label: 'Clinic settings', to: '/settings', icon: Settings },
]

function initials(user: { first_name: string; last_name: string }) {
  return `${user.first_name[0] ?? ''}${user.last_name[0] ?? ''}`.toUpperCase()
}

/** /patients/123 still highlights "Patients"; "/" only matches the dashboard itself. */
function isActive(pathname: string, to: string) {
  return to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`)
}

function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  const { pathname } = useLocation()
  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.to}>
              {item.soon ? (
                <SidebarMenuButton disabled tooltip={`${item.label} (coming soon)`}>
                  <item.icon />
                  <span>{item.label}</span>
                </SidebarMenuButton>
              ) : (
                <SidebarMenuButton asChild isActive={isActive(pathname, item.to)} tooltip={item.label}>
                  <NavLink to={item.to} end>
                    <item.icon />
                    <span>{item.label}</span>
                  </NavLink>
                </SidebarMenuButton>
              )}
              {item.soon && <SidebarMenuBadge>Soon</SidebarMenuBadge>}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

/** Switch between clinics, for users who work at more than one. */
function ClinicSwitcher() {
  const { me, membership, switchClinic } = useAuth()
  if (!me || !membership) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton size="lg">
          <span className="flex aspect-square size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Stethoscope className="size-4" />
          </span>
          <span className="grid flex-1 text-left leading-tight">
            <span className="truncate font-semibold">{membership.clinic_name}</span>
            <span className="truncate text-xs text-muted-foreground">
              {ROLE_LABELS[membership.role]}
            </span>
          </span>
          {me.memberships.length > 1 && <ChevronsUpDown className="ml-auto" />}
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      {me.memberships.length > 1 && (
        <DropdownMenuContent align="start" className="min-w-56">
          <DropdownMenuLabel className="text-xs text-muted-foreground">Your clinics</DropdownMenuLabel>
          {me.memberships.map((m) => (
            <DropdownMenuItem key={m.clinic_id} onSelect={() => switchClinic(m.clinic_id)}>
              <span className="flex-1 truncate">{m.clinic_name}</span>
              {m.clinic_id === membership.clinic_id && <Check className="size-4" />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      )}
    </DropdownMenu>
  )
}

function UserMenu() {
  const { me, signOut } = useAuth()
  if (!me) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton size="lg">
          <Avatar className="size-8 rounded-md">
            <AvatarFallback className="rounded-md">{initials(me.user)}</AvatarFallback>
          </Avatar>
          <span className="grid flex-1 text-left leading-tight">
            <span className="truncate font-medium">{me.user.full_name}</span>
            <span className="truncate text-xs text-muted-foreground">{me.user.email}</span>
          </span>
          <ChevronsUpDown className="ml-auto" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="min-w-56">
        <DropdownMenuItem onSelect={() => signOut()}>
          <LogOut />
          Log out
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => signOut(true)}>
          <MonitorSmartphone />
          Log out of all devices
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}


export function AppLayout() {
  const { pathname } = useLocation()
  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <ClinicSwitcher />
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <NavGroup label="Clinic" items={CLINIC_NAV} />
          <NavGroup label="Administration" items={ADMIN_NAV} />
        </SidebarContent>
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <UserMenu />
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          <span className="text-sm font-medium">
            {pathname.startsWith('/consultations/')
              ? 'Consultation'
              : ([...CLINIC_NAV, ...ADMIN_NAV].find((item) => isActive(pathname, item.to))?.label ??
                'Doctoo')}
          </span>
        </header>
        <div className="flex-1 p-4 md:p-6">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
