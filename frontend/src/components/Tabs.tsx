import { NavLink } from 'react-router-dom'

type TabDef = { to: string; label: string; showCounter?: boolean }

const TABS: TabDef[] = [
  { to: '/dashboard', label: 'Дашборд' },
  { to: '/komplektaciya', label: 'Комплектация', showCounter: true },
  { to: '/zakupka', label: 'В закупке', showCounter: true },
  { to: '/soprovozhdenie', label: 'В сопровождении', showCounter: true },
  { to: '/oplaty', label: 'Оплаты', showCounter: true },
  { to: '/otchety', label: 'Отчёты' },
]

export function Tabs() {
  return (
    <div className="tabs">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          className={({ isActive }) => (isActive ? 'tab active' : 'tab')}
        >
          {t.label}
          {t.showCounter && <b>—</b>}
        </NavLink>
      ))}
    </div>
  )
}
