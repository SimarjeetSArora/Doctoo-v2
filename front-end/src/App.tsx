import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'

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
          { path: '/team', element: <TeamPage /> },
          { path: '/settings', element: <ClinicSettingsPage /> },
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
