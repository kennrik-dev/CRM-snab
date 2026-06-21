import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { CommandBar } from './components/CommandBar'
import { Tabs } from './components/Tabs'

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="wrap">
      <div className="page-h">
        <h1>{title}</h1>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  )
}

export default App
