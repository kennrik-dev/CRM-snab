import { useMemo, useState, useEffect, type CSSProperties, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listPayments,
  getPaymentsSummary,
  createPayment,
  type PaymentListItem,
  type PaymentSort,
  type PaymentCreate,
} from '../api/payments'
import { buildPayBar } from '../lib/payView'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { Chip } from '../components/Chip'
import { Modal } from '../components/Modal'
import { payStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { rublesToKopecks } from '../lib/money'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

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
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')
  const [addOpen, setAddOpen] = useState(false)

  const createMut = useMutation({
    mutationFn: (payload: PaymentCreate) => createPayment(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['payments'] })
      setAddOpen(false)
    },
  })

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

      <FilterBar
        actions={
          canEditThis ? (
            <button className="btn primary" onClick={() => setAddOpen(true)}>
              + Добавить УПД
            </button>
          ) : undefined
        }
      >
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

      {addOpen && (
        <AddUpdModal
          onClose={() => setAddOpen(false)}
          onCreate={(payload) => createMut.mutate(payload)}
          pending={createMut.isPending}
        />
      )}
    </div>
  )
}

// ---- Add-УПД modal (manual) -----------------------------------------------

const addFieldStyle: CSSProperties = {
  padding: '6px 8px',
  border: '1px solid var(--line)',
  borderRadius: 4,
  fontSize: 13,
  background: 'var(--surface)',
  width: '100%',
}
const addLabelStyle: CSSProperties = {
  fontSize: 10,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'var(--faint)',
  fontWeight: 600,
  marginBottom: 3,
  display: 'block',
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <span style={addLabelStyle}>{label}</span>
      {children}
    </div>
  )
}

// Mount-controlled (like SplitDialog in ProcedureCard): the parent renders
// `{addOpen && <AddUpdModal .../>}` so each open gets a fresh form state.
function AddUpdModal({
  onClose,
  onCreate,
  pending,
}: {
  onClose: () => void
  onCreate: (payload: PaymentCreate) => void
  pending: boolean
}) {
  const [f, setF] = useState({
    upd: '',
    request_label: '',
    supplier: '',
    srok: '',
    amount: '',
    zrds: '',
  })
  const valid = f.upd.trim() !== ''

  function submit() {
    if (!valid || pending) return
    onCreate({
      upd: f.upd.trim(),
      request_label: f.request_label.trim() || undefined,
      supplier: f.supplier.trim() || undefined,
      srok: f.srok || undefined,
      amount: rublesToKopecks(f.amount) ?? undefined,
      zrds: f.zrds.trim() || undefined,
    })
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Добавить УПД"
      width={560}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={pending}>
            Отмена
          </button>
          <button className="btn primary" onClick={submit} disabled={!valid || pending}>
            {pending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label="№ УПД *">
          <input
            style={addFieldStyle}
            value={f.upd}
            onChange={(e) => setF((s) => ({ ...s, upd: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Заявка">
          <input
            style={addFieldStyle}
            placeholder="Т-67 + №"
            value={f.request_label}
            onChange={(e) => setF((s) => ({ ...s, request_label: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Поставщик">
          <input
            style={addFieldStyle}
            value={f.supplier}
            onChange={(e) => setF((s) => ({ ...s, supplier: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Срок">
          <input
            type="date"
            style={addFieldStyle}
            value={f.srok}
            onChange={(e) => setF((s) => ({ ...s, srok: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="Сумма с НДС (₽)">
          <input
            style={addFieldStyle}
            inputMode="decimal"
            placeholder="0,00"
            value={f.amount}
            onChange={(e) => setF((s) => ({ ...s, amount: e.target.value }))}
            disabled={pending}
          />
        </Field>
        <Field label="№ ЗРДС">
          <input
            style={addFieldStyle}
            value={f.zrds}
            onChange={(e) => setF((s) => ({ ...s, zrds: e.target.value }))}
            disabled={pending}
          />
        </Field>
      </div>
    </Modal>
  )
}
