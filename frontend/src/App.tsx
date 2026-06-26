import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandBar } from './components/CommandBar'
import { Tabs } from './components/Tabs'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Login } from './auth/Login'
import { ChangePassword } from './auth/ChangePassword'
import { RequireAuth, RequireAuthOrChange, RequireNoAuth } from './auth/Guards'
import { Komplektaciya } from './pages/Komplektaciya'
import { Zakupka } from './pages/Zakupka'
import { Soprovozhdenie } from './pages/Soprovozhdenie'
import { Oplaty } from './pages/Oplaty'
import { RequestCard } from './cards/RequestCard'
import { ProcedureCard } from './cards/ProcedureCard'
import { SupportCard } from './cards/SupportCard'

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="wrap">
      <div className="page-h">
        <h1>{title}</h1>
      </div>
    </div>
  )
}

function AppShell() {
  return (
    <>
      <CommandBar />
      <Tabs />
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<PlaceholderPage title="Дашборд" />} />
        <Route path="/komplektaciya" element={<Komplektaciya />} />
        <Route path="/komplektaciya/:id" element={<RequestCard />} />
        <Route path="/zakupka" element={<Zakupka />} />
        <Route path="/zakupka/:id" element={<ProcedureCard />} />
        <Route path="/soprovozhdenie" element={<Soprovozhdenie />} />
        <Route path="/soprovozhdenie/:id" element={<SupportCard />} />
        <Route path="/oplaty" element={<Oplaty />} />
        <Route path="/otchety" element={<PlaceholderPage title="Отчёты" />} />
      </Routes>
    </>
  )
}

function LoadingScreen() {
  return <div className="app-loading">Загрузка…</div>
}

function Router() {
  const { status } = useAuth()
  if (status === 'loading') return <LoadingScreen />
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RequireNoAuth>
            <Login />
          </RequireNoAuth>
        }
      />
      <Route
        path="/change-password"
        element={
          <RequireAuthOrChange>
            <ChangePassword />
          </RequireAuthOrChange>
        }
      />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      />
    </Routes>
  )
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Router />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
