import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ApiError } from './api/client'
import App from './App'
import './i18n'
import './index.css'

// A 4xx answer (locked, forbidden, not found) will not change by asking again; only retry network/server faults.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
