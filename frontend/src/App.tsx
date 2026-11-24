import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import ComingSoon from './pages/ComingSoon'
import JournalForm from './pages/JournalForm'
import JournalList from './pages/JournalList'
import Login from './pages/Login'
import Shell from './pages/Shell'
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
        <Route path="treasury" element={<ComingSoon titleKey="nav.treasury" />} />
        <Route path="inventory" element={<ComingSoon titleKey="nav.inventory" />} />
        <Route path="reports" element={<ComingSoon titleKey="nav.reports" />} />
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
