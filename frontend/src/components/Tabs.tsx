import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRequests } from '../api/requests'
import { listProcurements } from '../api/procedures'
import { listSupport } from '../api/support'
import { listPayments } from '../api/payments'

type TabDef = { to: string; label: string; showCounter?: boolean }

const TABS: TabDef[] = [
  { to: '/dashboard', label: 'Дашборд' },
  { to: '/komplektaciya', label: 'Комплектация', showCounter: true },
  { to: '/zakupka', label: 'В закупке', showCounter: true },
  { to: '/soprovozhdenie', label: 'В сопровождении', showCounter: true },
  { to: '/oplaty', label: 'Оплаты', showCounter: true },
  { to: '/otchety', label: 'Отчёты' },
]

// Counter queries fetch page_size=1 so the backend only sends the `total`
// count and no payload rows. The «Оплаты» counter = unpaid УПД
// (hide_paid=true → total is the await count).
const KOMPL_COUNTER_KEY = ['requests', { tabCounter: true }] as const
const ZAKUP_COUNTER_KEY = ['procurements', { tabCounter: true }] as const
const SOPP_COUNTER_KEY = ['support', { tabCounter: true }] as const
const OPLAT_COUNTER_KEY = ['payments', { tabCounter: true }] as const

export function Tabs() {
  const kompl = useQuery({
    queryKey: KOMPL_COUNTER_KEY,
    queryFn: () => listRequests({ page_size: 1 }),
  })
  const zakup = useQuery({
    queryKey: ZAKUP_COUNTER_KEY,
    queryFn: () => listProcurements({ page_size: 1 }),
  })
  const sopp = useQuery({
    queryKey: SOPP_COUNTER_KEY,
    queryFn: () => listSupport({ page_size: 1 }),
  })
  const oplat = useQuery({
    queryKey: OPLAT_COUNTER_KEY,
    queryFn: () => listPayments({ hide_paid: true, page_size: 1 }),
  })
  const komplTotal = kompl.data?.total
  const zakupTotal = zakup.data?.total
  const soppTotal = sopp.data?.total
  const oplatTotal = oplat.data?.total

  return (
    <div className="tabs">
      {TABS.map((t) => {
        const count =
          t.to === '/komplektaciya'
            ? (komplTotal ?? '—')
            : t.to === '/zakupka'
              ? (zakupTotal ?? '—')
              : t.to === '/soprovozhdenie'
                ? (soppTotal ?? '—')
                : t.to === '/oplaty'
                  ? (oplatTotal ?? '—')
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
