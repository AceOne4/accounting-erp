import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import Accounts from './pages/Accounts'
import Inventory from './pages/Inventory'
import JournalForm from './pages/JournalForm'
import JournalList from './pages/JournalList'
import Login from './pages/Login'
import Partners from './pages/Partners'
import Reports from './pages/Reports'
import Shell from './pages/Shell'
import Treasury from './pages/Treasury'
import Users from './pages/Users'
import { SessionProvider, useSession } from './session'

function Gate() {
  const { user, loading } = useSession()
  if (loading) return <div className="p-6">…</div>
  if (!user) return <Login />
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Navigate to="/journal" replace />} />
        <Route path="journal" element={<JournalList />} />
        <Route path="journal/new" element={<JournalForm />} />
        <Route path="journal/:id" element={<JournalForm />} />
        <Route path="partners" element={<Partners />} />
        <Route path="accounts" element={<Accounts />} />
        <Route path="treasury" element={<Treasury />} />
        <Route path="inventory/*" element={<Inventory />} />
        <Route path="reports/*" element={<Reports />} />
        <Route path="users" element={<Users />} />
        <Route path="*" element={<Navigate to="/journal" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Gate />
      </SessionProvider>
    </BrowserRouter>
  )
}
