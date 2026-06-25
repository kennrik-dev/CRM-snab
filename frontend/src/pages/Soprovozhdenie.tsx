import { useMemo, useState, useCallback, useEffect, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listSupport,
  STATUS_POSTAVKI,
  type SupportListItem,
  type SupportSort,
} from '../api/support'
import { listDict } from '../api/dict'
import { patchProcedure, type ProcedurePatch } from '../api/procedures'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { StatusSelect } from '../components/StatusSelect'
import { Chip } from '../components/Chip'
import { OverduePct } from '../components/support/OverduePct'
import { Progress } from '../components/support/Progress'
import { DocsSquares } from '../components/support/DocsSquares'
import { sdelkiStatusChip, postavkiStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

type Numbered = SupportListItem & { _idx: number }

const SORT_OPTIONS: { value: SupportSort; label: string }[] = [
  { value: 'created_at', label: 'По дате создания' },
  { value: 'code', label: 'По коду' },
  { value: 'proc', label: 'По № процедуры' },
  { value: 'supplier', label: 'По поставщику' },
  { value: 'contract_sum', label: 'По сумме договора' },
  { value: 'status_postavki', label: 'По статусу поставки' },
  { value: 'status_sdelki', label: 'По статусу сделки' },
  { value: 'srok_dd', label: 'По сроку ДД' },
  { value: 'plan_date', label: 'По плану' },
  { value: 'fakt_date', label: 'По факту' },
]

// ---- Search debounce ------------------------------------------------------

function useDebounced<T>(value: T, delay: number): T {
  const [v, setV] = useState(value)
  // The setState in this effect commits the *latest* `value` to `v` only
  // after `delay` has elapsed. Each new `value` cancels the previous timer.
  // Standard debounce pattern; the setState happens inside a setTimeout
  // callback (not synchronously in the effect body), so the cascading-render
  // lint rule is safe to disable here.
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), delay)
    return () => window.clearTimeout(t)
  }, [value, delay])
  return v
}

// ---- Column definitions ---------------------------------------------------

// `_idx` carries the row's 1-based position (the `#` column). The DataTable
// render callback receives a single row, so rows are pre-numbered before being
// handed to the table. Widths sum to EXACTLY 100% (table-layout: fixed):
// 3+16+6+5+8+7+8+9+9+6+6+6+5+6+6 = 100.
function buildColumns(args: {
  sdelkiOptions: string[] | null
  onSdelki: (id: number, v: string) => void
  onPostavki: (id: number, v: string) => void
  onDate: (id: number, field: 'plan_date' | 'fakt_date', v: string) => void
  canEdit: boolean
}): DataTableColumn<Numbered>[] {
  const { sdelkiOptions, onSdelki, onPostavki, onDate, canEdit } = args
  return [
    {
      key: '_idx',
      header: '#',
      align: 'center',
      width: '3%',
      render: (r) => <span className="num">{r._idx + 1}</span>,
    },
    {
      key: 'title',
      header: 'Наименование',
      width: '16%',
      render: (r) => (
        <>
          <span className="parent-tag">{r.code}</span>
          <span className="zname">{r.title}</span>
        </>
      ),
    },
    {
      key: 'tender_num',
      header: '№ заявки',
      width: '6%',
      render: (r) => (
        <span className="zaglink">{r.tender_num ?? '—'}</span>
      ),
    },
    {
      key: 'proc',
      header: '№ процед.',
      width: '5%',
      render: (r) => <span className="proc-id">{r.proc ?? '—'}</span>,
    },
    {
      key: 'supplier',
      header: 'Поставщик',
      width: '8%',
      render: (r) =>
        r.supplier ? (
          <span className="supp-c">{r.supplier}</span>
        ) : (
          <span className="supp-c empty">—</span>
        ),
    },
    {
      key: 'mtr',
      header: 'Тип МТР',
      width: '7%',
      render: (r) => r.mtr ?? '—',
    },
    {
      key: 'contract_sum',
      header: 'Сумма дог.',
      align: 'right',
      width: '8%',
      render: (r) => <span className="dt">{money(r.contract_sum)}</span>,
    },
    {
      key: 'status_sdelki',
      header: 'Статус сделки',
      width: '9%',
      render: (r) =>
        canEdit ? (
          <StatusSelect
            value={r.status_sdelki}
            options={sdelkiOptions ?? []}
            onSelect={(v) => onSdelki(r.id, v)}
            color={sdelkiStatusChip}
          />
        ) : (
          <Chip {...sdelkiStatusChip(r.status_sdelki)} mini />
        ),
    },
    {
      key: 'status_postavki',
      header: 'Статус поставки',
      width: '9%',
      render: (r) =>
        canEdit ? (
          <StatusSelect
            value={r.status_postavki}
            options={[...STATUS_POSTAVKI]}
            onSelect={(v) => onPostavki(r.id, v)}
            color={postavkiStatusChip}
          />
        ) : (
          <Chip {...postavkiStatusChip(r.status_postavki)} mini />
        ),
    },
    {
      key: 'srok_dd',
      header: 'Срок ДД',
      width: '6%',
      render: (r) => <span className="dt">{dateRu(r.srok_dd)}</span>,
    },
    {
      key: 'plan_date',
      header: 'План',
      width: '6%',
      render: (r) =>
        canEdit ? (
          <input
            type="date"
            value={r.plan_date ?? ''}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onDate(r.id, 'plan_date', e.target.value)}
            style={{
              border: '1px solid var(--line)',
              borderRadius: 4,
              padding: '2px 4px',
              fontFamily: 'inherit',
              fontSize: 12,
            }}
          />
        ) : (
          <span className="dt">{dateRu(r.plan_date)}</span>
        ),
    },
    {
      key: 'fakt_date',
      header: 'Факт',
      width: '6%',
      render: (r) =>
        canEdit ? (
          <input
            type="date"
            value={r.fakt_date ?? ''}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onDate(r.id, 'fakt_date', e.target.value)}
            style={{
              border: '1px solid var(--line)',
              borderRadius: 4,
              padding: '2px 4px',
              fontFamily: 'inherit',
              fontSize: 12,
            }}
          />
        ) : (
          <span className="dt">{dateRu(r.fakt_date)}</span>
        ),
    },
    {
      key: 'overdue_pct',
      header: 'Просроч.',
      align: 'center',
      width: '5%',
      render: (r) => <OverduePct overduePct={r.overdue_pct} />,
    },
    {
      key: 'docs',
      header: 'Док-ты',
      align: 'center',
      width: '6%',
      render: (r) => <DocsSquares docs={r.docs} />,
    },
    {
      key: 'progress',
      header: 'Поз.',
      align: 'center',
      width: '6%',
      render: (r) => (
        <Progress delivered={r.progress_delivered} total={r.progress_total} />
      ),
    },
  ]
}

// ---- Page -----------------------------------------------------------------

export function Soprovozhdenie() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')

  const [searchInput, setSearchInput] = useState('')
  const [nonSearch, setNonSearch] = useState<{ include_archived: boolean; sort: SupportSort }>({
    include_archived: false,
    sort: 'created_at',
  })
  const debouncedSearch = useDebounced(searchInput, 300)

  const list = useQuery({
    queryKey: ['support', { search: debouncedSearch, ...nonSearch }],
    queryFn: () =>
      listSupport({
        search: debouncedSearch || undefined,
        include_archived: nonSearch.include_archived || undefined,
        sort: nonSearch.sort,
        page: 1,
        page_size: 100,
      }),
  })

  // Dict for the inline «Статус сделки» <select> (3 значения).
  const sdelkiDict = useQuery({
    queryKey: ['dict', 'status_sdelki'],
    queryFn: () => listDict('status_sdelki'),
  })
  const sdelkiOptions = sdelkiDict.data?.map((d) => d.value) ?? null

  // In-row Б2 patch: status_sdelki / status_postavki / plan_date / fakt_date.
  // Each PATCH returns the updated procedure; on success the list refetches.
  const patchMut = useMutation({
    mutationFn: (vars: { id: number; patch: ProcedurePatch }) =>
      patchProcedure(vars.id, vars.patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['support'] }),
    onError: (err) => console.error('support patch failed', err),
  })
  const onSdelki = useCallback(
    (id: number, v: string) => patchMut.mutate({ id, patch: { status_sdelki: v } }),
    [patchMut],
  )
  const onPostavki = useCallback(
    (id: number, v: string) => patchMut.mutate({ id, patch: { status_postavki: v } }),
    [patchMut],
  )
  const onDate = useCallback(
    (id: number, field: 'plan_date' | 'fakt_date', v: string) =>
      patchMut.mutate({
        id,
        patch: field === 'plan_date' ? { plan_date: v || null } : { fakt_date: v || null },
      }),
    [patchMut],
  )

  const items = useMemo(() => list.data?.items ?? [], [list.data])
  const numbered: Numbered[] = useMemo(
    () => items.map((r, i) => ({ ...r, _idx: i })),
    [items],
  )
  const total = list.data?.total ?? 0

  const columns = useMemo(
    () =>
      buildColumns({ sdelkiOptions, onSdelki, onPostavki, onDate, canEdit: canEditThis }),
    [sdelkiOptions, onSdelki, onPostavki, onDate, canEditThis],
  )

  const hasFilterApplied =
    debouncedSearch.trim() !== '' || nonSearch.include_archived

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>В сопровождении</h1>
        <span className="desc">
          Процедуры после закупки: договор, поставки, документы, УПД.
        </span>
        <span className="sp" />
      </div>

      <FilterBar>
        <input
          type="text"
          className="rep-sel"
          style={{ minWidth: 220 }}
          placeholder="Поиск: Т-67, № заявки, поставщик, договор, № УПД…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          className="rep-sel"
          value={nonSearch.sort}
          onChange={(e) =>
            setNonSearch((s) => ({ ...s, sort: e.target.value as SupportSort }))
          }
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
          }}
        >
          <input
            type="checkbox"
            checked={nonSearch.include_archived}
            onChange={(e) =>
              setNonSearch((s) => ({ ...s, include_archived: e.target.checked }))
            }
          />
          Показать завершённые/отменённые
        </label>
      </FilterBar>

      <div className="block" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
        <div className="block-h">
          <span className="bnum">С</span>
          <div>
            <div className="btitle">В сопровождении</div>
            <div className="beng">In support</div>
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
                (list.error as { body?: { detail?: string } })?.body?.detail ??
                  list.error,
              )}
            />
          ) : (
            <DataTable<Numbered>
              columns={columns}
              rows={numbered}
              getRowId={(r) => r.id}
              onRowClick={(row) => navigate(`/soprovozhdenie/${row.id}`)}
              empty={
                <EmptyState
                  title={hasFilterApplied ? 'Ничего не найдено' : 'Нет процедур в сопровождении'}
                  hint={
                    hasFilterApplied
                      ? undefined
                      : 'Процедуры появляются здесь после «Передать в сопровождение» в закупке.'
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
