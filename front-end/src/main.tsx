import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError } from '@/lib/api'

import App from './App.tsx'
import './index.css'

// Caches server data and handles loading/error states for every API call.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't retry "not allowed" / "not found" style errors; they won't fix themselves.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status < 500) && failureCount < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <App />
        <Toaster richColors position="top-right" />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
