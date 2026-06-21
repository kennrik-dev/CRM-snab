import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/zakupki-crm.css'
import './components/excel-table.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
