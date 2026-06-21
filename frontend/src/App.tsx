import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { CommandBar } from './components/CommandBar'
import { Tabs } from './components/Tabs'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Login } from './auth/Login'
import { ChangePassword } from './auth/ChangePassword'
import { RequireAuth, RequireNoAuth } from './auth/Guards'

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
        <Route path="/komplektaciya" element={<PlaceholderPage title="Комплектация" />} />
        <Route path="/zakupka" element={<PlaceholderPage title="В закупке" />} />
        <Route path="/soprovozhdenie" element={<PlaceholderPage title="В сопровождении" />} />
        <Route path="/oplaty" element={<PlaceholderPage title="Оплаты" />} />
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
          <RequireAuth>
            <ChangePassword />
          </RequireAuth>
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

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Router />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App