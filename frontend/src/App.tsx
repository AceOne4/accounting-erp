import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'

import ErrorBoundary from './components/ErrorBoundary'
import Home from './pages/Home'
import JournalForm from './pages/JournalForm'
import JournalList from './pages/JournalList'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Shell from './pages/Shell'
import { SessionProvider } from './session'
import { useSession } from './sessionContext'

// Heavier screens load when first opened.
const Accounts = lazy(() => import('./pages/Accounts'))
const Inventory = lazy(() => import('./pages/Inventory'))
const Partners = lazy(() => import('./pages/Partners'))
const Reports = lazy(() => import('./pages/Reports'))
const Treasury = lazy(() => import('./pages/Treasury'))
const Users = lazy(() => import('./pages/Users'))

function Gate() {
  const { user, loading } = useSession()
  if (loading) return <div className="p-6">…</div>
  if (!user) return <Login />
  return (
    <Suspense fallback={<div className="p-6">…</div>}>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Home />} />
          <Route path="journal" element={<JournalList />} />
          <Route path="journal/new" element={<JournalForm />} />
          <Route path="journal/:id" element={<JournalForm />} />
          <Route path="partners" element={<Partners />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="treasury" element={<Treasury />} />
          <Route path="inventory/*" element={<Inventory />} />
          <Route path="reports/*" element={<Reports />} />
          <Route path="users" element={<Users />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <SessionProvider>
          <Gate />
        </SessionProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
