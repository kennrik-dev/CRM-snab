import { useMemo, useState, useEffect, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  listPayments,
  getPaymentsSummary,
  type PaymentListItem,
  type PaymentSort,
} from '../api/payments'
import { buildPayBar } from '../lib/payView'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { Chip } from '../components/Chip'
import { payStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'

const SORT_OPTIONS: { value: PaymentSort; label: string }[] = [
  { value: 'created_at', label: 'По дате создания' },
  { value: 'upd', label: 'По № УПД' },
  { value: 'request', label: 'По заявке' },
  { value: 'supplier', label: 'По поставщику' },
  { value: 'contract', label: 'По договору' },
  { value: 'zrds', label: 'По ЗРДС' },
  { value: 'status', label: 'По статусу оплаты' },
  { value: 'srok', label: 'По сроку' },
  { value: 'amount', label: 'По сумме' },
]

// Search debounce (same pattern as Soprovozhdenie — duplicated intentionally,
// see plan Global Constraints).
function useDebounced<T>(value: T, delay: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), delay)
    return () => window.clearTimeout(t)
  }, [value, delay])
  return v
}

// ---- Summary hero + distribution bar --------------------------------------

function PaySummary() {
  const q = useQuery({
    queryKey: ['payments', 'summary'],
    queryFn: getPaymentsSummary,
  })
  if (q.isError) return null
  if (!q.data) {
    // Loading skeleton: 4 empty cards so the layout doesn't jump.
    return (
      <div className="payhero">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="pcard" style={{ '--c': 'var(--line)' } as CSSProperties}>
            <div className="pl">…</div>
            <div className="pv">…</div>
          </div>
        ))}
      </div>
    )
  }
  const m = q.data.meters
  const segs = buildPayBar(q.data.bar).filter((s) => s.value > 0)
  const card = (label: string, val: number, token: string, sub?: string) => (
    <div className="pcard" style={{ '--c': `var(--${token})` } as CSSProperties}>
      <div className="pl">{label}</div>
      <div className="pv">{money(val)}</div>
      {sub && <div className="pvsub">{sub}</div>}
    </div>
  )
  return (
    <>
      <div className="payhero">
        {card('Сумма в работе', m.in_work, 'ink', 'оплачено + к оплате')}
        {card('Оплачено', m.paid, 'ok')}
        {card('К оплате', m.await_, 'proc')}
        {card('Просрочено', m.overdue, 'late')}
      </div>
      <div className="pbar">
        {segs.map((s) => (
          <span key={s.cls} className={s.cls} style={{ width: `${s.widthPct}%` }}>
            {s.labelPct}%
          </span>
        ))}
      </div>
    </>
  )
}

// ---- Page -----------------------------------------------------------------

export function Oplaty() {
  const navigate = useNavigate()

  const [searchInput, setSearchInput] = useState('')
  const [nonSearch, setNonSearch] = useState<{ hide_paid: boolean; sort: PaymentSort }>({
    hide_paid: false,
    sort: 'created_at',
  })
  const debouncedSearch = useDebounced(searchInput, 300)

  const list = useQuery({
    queryKey: ['payments', { search: debouncedSearch, ...nonSearch }],
    queryFn: () =>
      listPayments({
        search: debouncedSearch || undefined,
        hide_paid: nonSearch.hide_paid || undefined,
        sort: nonSearch.sort,
        page: 1,
        page_size: 100,
      }),
  })

  const items = useMemo(() => list.data?.items ?? [], [list.data])
  const total = list.data?.total ?? 0

  const columns = useMemo<DataTableColumn<PaymentListItem>[]>(
    () => [
      {
        key: 'upd',
        header: 'УПД',
        width: '11%',
        render: (r) => <span className="updn">{r.upd}</span>,
      },
      {
        key: 'request_display',
        header: 'Заявка',
        width: '12%',
        render: (r) => r.request_display ?? '—',
      },
      {
        key: 'supplier',
        header: 'Поставщик',
        width: '15%',
        render: (r) => r.supplier ?? '—',
      },
      {
        key: 'contract',
        header: 'Договор',
        width: '12%',
        render: (r) => r.contract ?? '—',
      },
      {
        key: 'zrds',
        header: 'ЗРДС',
        width: '10%',
        render: (r) => r.zrds ?? '—',
      },
      {
        key: 'delivery_n',
        header: 'Поставка',
        width: '7%',
        align: 'center',
        render: (r) => r.delivery_n ?? '—',
      },
      {
        key: 'pay_status',
        header: 'Статус',
        width: '12%',
        render: (r) => <Chip {...payStatusChip(r.pay_status, r.is_overdue)} mini />,
      },
      {
        key: 'srok',
        header: 'Срок',
        width: '8%',
        render: (r) => dateRu(r.srok),
      },
      {
        key: 'amount',
        header: 'Сумма',
        width: '13%',
        align: 'right',
        render: (r) => <span className="dt">{money(r.amount)}</span>,
      },
    ],
    [],
  )

  const hasFilterApplied = debouncedSearch.trim() !== '' || nonSearch.hide_paid

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>Оплаты</h1>
        <span className="desc">реестр платежей по УПД</span>
        <span className="sp" />
      </div>

      <PaySummary />

      <FilterBar>
        <input
          type="text"
          className="rep-sel"
          style={{ minWidth: 220 }}
          placeholder="Поиск: № УПД, заявка, поставщик, договор, ЗРДС…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          className="rep-sel"
          value={nonSearch.sort}
          onChange={(e) => setNonSearch((s) => ({ ...s, sort: e.target.value as PaymentSort }))}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={nonSearch.hide_paid}
            onChange={(e) => setNonSearch((s) => ({ ...s, hide_paid: e.target.checked }))}
          />
          Скрыть оплаченные
        </label>
      </FilterBar>

      <div className="block" style={{ '--bc': 'var(--pay)' } as CSSProperties}>
        <div className="block-h">
          <span className="bnum">О</span>
          <div>
            <div className="btitle">Реестр платежей</div>
            <div className="beng">Payments</div>
          </div>
          <span className="bcount">{total}</span>
          <span className="sp" />
        </div>
        <div className="tbl-scroll">
          {list.isLoading ? (
            <div className="empty-state">Загрузка…</div>
          ) : list.isError ? (
            <EmptyState
              title="Ошибка загрузки"
              hint={String(
                (list.error as { body?: { detail?: string } })?.body?.detail ?? list.error,
              )}
            />
          ) : (
            <DataTable<PaymentListItem>
              className="fit"
              columns={columns}
              rows={items}
              getRowId={(r) => r.id}
              onRowClick={(row) => navigate(`/oplaty/${row.id}`)}
              empty={
                <EmptyState
                  title={hasFilterApplied ? 'Ничего не найдено' : 'Нет платежей'}
                  hint={
                    hasFilterApplied
                      ? undefined
                      : 'УПД появляются здесь автоматически из поставок или кнопкой «+ Добавить УПД».'
                  }
                />
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}
