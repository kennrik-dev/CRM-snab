import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRequests } from '../api/requests'

type TabDef = { to: string; label: string; showCounter?: boolean }

const TABS: TabDef[] = [
  { to: '/dashboard', label: 'Дашборд' },
  { to: '/komplektaciya', label: 'Комплектация', showCounter: true },
  { to: '/zakupka', label: 'В закупке', showCounter: true },
  { to: '/soprovozhdenie', label: 'В сопровождении', showCounter: true },
  { to: '/oplaty', label: 'Оплаты', showCounter: true },
  { to: '/otchety', label: 'Отчёты' },
]

// Single shared query for all tab counters. We fetch page_size=1 so the
// backend only sends the `total` count and no payload rows.
// Other tabs (zakupka, soprovozhdenie, oplaty) are placeholders for now — they
// still render `—` until their endpoints are wired up.
const COUNTERS_QUERY_KEY = ['requests', { tabCounter: true }] as const

function useTabCounters() {
  return useQuery({
    queryKey: COUNTERS_QUERY_KEY,
    queryFn: () => listRequests({ page_size: 1 }),
  })
}

export function Tabs() {
  const counters = useTabCounters()
  const komplTotal = counters.data?.total

  return (
    <div className="tabs">
      {TABS.map((t) => {
        const count =
          t.to === '/komplektaciya'
            ? (komplTotal ?? '—')
            : t.showCounter
              ? '—'
              : null
        return (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) => (isActive ? 'tab active' : 'tab')}
          >
            {t.label}
            {count !== null && <b>{count}</b>}
          </NavLink>
        )
      })}
    </div>
  )
}
