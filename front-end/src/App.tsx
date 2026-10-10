import { createBrowserRouter, RouterProvider } from 'react-router'

import { SystemStatusPage } from '@/features/system/SystemStatusPage'

// URL → page mapping. Login, patients, appointments, etc. get added here as we build them.
const router = createBrowserRouter([{ path: '/', element: <SystemStatusPage /> }])

export default function App() {
  return <RouterProvider router={router} />
}
