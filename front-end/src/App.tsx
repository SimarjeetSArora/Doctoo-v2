import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'

import { AppointmentsPage } from '@/features/appointments/AppointmentsPage'
import { DoctorHoursPage } from '@/features/appointments/DoctorHoursPage'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { ForgotPasswordPage } from '@/features/auth/ForgotPasswordPage'
import { GuestOnly, RequireAuth } from '@/features/auth/guards'
import { InvitePage } from '@/features/auth/InvitePage'
import { LoginPage } from '@/features/auth/LoginPage'
import { OnboardingPage } from '@/features/auth/OnboardingPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { ResetPasswordPage } from '@/features/auth/ResetPasswordPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ClinicSettingsPage } from '@/features/settings/ClinicSettingsPage'
import { PatientAuthProvider, PatientGuestOnly, RequirePatient } from '@/features/patient-app/patient-auth'
import { PatientLayout } from '@/features/patient-app/PatientLayout'
import { PatientLoginPage } from '@/features/patient-app/PatientLoginPage'
import { ProfilePage } from '@/features/patient-app/ProfilePage'
import { ProfilesPage } from '@/features/patient-app/ProfilesPage'
import { PatientDetailPage } from '@/features/patients/PatientDetailPage'
import { EditPatientPage, NewPatientPage } from '@/features/patients/PatientFormPages'
import { PatientsPage } from '@/features/patients/PatientsPage'
import { SystemStatusPage } from '@/features/system/SystemStatusPage'
import { TeamPage } from '@/features/team/TeamPage'
import { AppLayout } from '@/layouts/AppLayout'

// URL → page mapping. Guards decide who may see each group of pages.
const router = createBrowserRouter([
  {
    element: <GuestOnly />, // logged-out users only
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
    ],
  },
  // Opened from email links; work whether or not someone is logged in.
  { path: '/reset-password', element: <ResetPasswordPage /> },
  { path: '/invite', element: <InvitePage /> },
  { path: '/status', element: <SystemStatusPage /> },
  {
    element: <RequireAuth />, // logged-in users only
    children: [
      { path: '/onboarding', element: <OnboardingPage /> },
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/patients', element: <PatientsPage /> },
          { path: '/patients/new', element: <NewPatientPage /> },
          { path: '/patients/:patientId', element: <PatientDetailPage /> },
          { path: '/patients/:patientId/edit', element: <EditPatientPage /> },
          { path: '/appointments', element: <AppointmentsPage /> },
          { path: '/doctor-hours', element: <DoctorHoursPage /> },
          { path: '/team', element: <TeamPage /> },
          { path: '/settings', element: <ClinicSettingsPage /> },
        ],
      },
    ],
  },
  // Patient app: its own login, separate from clinic staff.
  {
    path: '/patient',
    element: <PatientAuthProvider />,
    children: [
      { element: <PatientGuestOnly />, children: [{ path: 'login', element: <PatientLoginPage /> }] },
      {
        element: <RequirePatient />,
        children: [
          {
            element: <PatientLayout />,
            children: [
              { index: true, element: <ProfilesPage /> },
              { path: 'profile/:profileId', element: <ProfilePage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  )
}
