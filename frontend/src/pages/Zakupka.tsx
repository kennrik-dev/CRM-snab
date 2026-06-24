import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Chip, type ChipKind } from '../components/Chip'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { FilterBar } from '../components/FilterBar'
import {
  listProcurements,
  patchProcedure,
  type ProcedureListItem,
  type ProcedureSort,
} from '../api/procedures'
import { listDict } from '../api/dict'
import { useAuth } from '../auth/AuthContext'
import { canEdit } from '../lib/permissions'
import { dateRu } from '../lib/format'
import { pluralRequests } from '../lib/plural'

type SortAndArchive = {
  include_archived: boolean
  sort: ProcedureSort
}

const DEFAULT_NON_SEARCH: SortAndArchive = {
  include_archived: false,
  sort: 'created_at',
}

// ---- Search debounce ------------------------------------------------------

function useDebounced<T>(value: T, delay: number): T {
  const [v, setV] = useState(value)
  // The setState in this effect commits the *latest* `value` to `v` only
  // after `delay` has elapsed. Each new `value` cancels the previous timer.
  // This is the standard debounce pattern; the setState happens inside a
  // setTimeout callback (not synchronously in the effect body), so it is
  // safe to disable the cascading-render lint rule here.
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), delay)
    return () => window.clearTimeout(t)
  }, [value, delay])
  return v
}

// ---- Status → chip mapping (pure, unit-tested) ----------------------------

// Each status_zakup value gets its OWN color (like Комплектация's colored
// chips), so the 6 справочник values + «Новая» + «Отменена» are visually
// distinct at a glance. Hues reuse the stage palette where they fit, plus a
// dedicated «teal» for «Согласование» (the stage palette only has 6 hues).
const STATUS_KIND: Record<string, ChipKind> = {
  'Приём заявок': 'proc',
  'Торги': 'supp',
  'Тех. экспертиза': 'pay',
  'Дозапросы': 'late',
  'Согласование': 'teal',
  'На сделку': 'ok',
}

export function procStatusChip(
  status_zakup: string | null | undefined,
): { kind: ChipKind; label: string } {
  if (status_zakup === 'Отменена') return { kind: 'cancel', label: 'Отменена' }
  if (!status_zakup || status_zakup === '') return { kind: 'wait', label: 'В закупке' }
  if (status_zakup === 'Новая') return { kind: 'wait', label: 'Новая' }
  return { kind: STATUS_KIND[status_zakup] ?? 'proc', label: status_zakup }
}

// ChipKind → CSS color vars, so the inline row <select> (editor) matches the
// colored chip (read-only). Exported for ProcedureCard's status select too.
export const STATUS_KIND_COLOR: Record<
  ChipKind,
  { color: string; background: string }
> = {
  wait: { color: 'var(--wait)', background: 'var(--wait-bg)' },
  proc: { color: 'var(--proc)', background: 'var(--proc-bg)' },
  supp: { color: 'var(--supp)', background: 'var(--supp-bg)' },
  pay: { color: 'var(--pay)', background: 'var(--pay-bg)' },
  ok: { color: 'var(--ok)', background: 'var(--ok-bg)' },
  late: { color: 'var(--late)', background: 'var(--late-bg)' },
  teal: { color: 'var(--teal)', background: 'var(--teal-bg)' },
  cancel: { color: 'var(--muted)', background: 'var(--wait-bg)' },
}

// ---- Procedure column definitions -----------------------------------------

// `_idx` carries the row's position in the displayed list (1-based index for
// the `#` column). The DataTable render callback receives a single row, so we
// pre-number rows before handing them to the table.
type NumberedProc = ProcedureListItem & { _idx: number }

function buildColumns({
  statusOptions,
  onStatusChange,
  canEdit,
}: {
  statusOptions: string[] | null
  onStatusChange: (id: number, status: string) => void
  canEdit: boolean
}): DataTableColumn<NumberedProc>[] {
  // Widths sum to EXACTLY 100% so the table fills `.tbl-scroll` and every
  // column keeps a STATIC width (table-layout: fixed + colgroup), mirroring
  // Komplektaciya.tsx. The wide «Наименование» column absorbs wrapping.
  // Status widened to 11% for the inline status <select>.
  // 3+17+8+7+8+14+9+9+9+5+11 = 100.
  return [
    {
      key: '_idx',
      header: '#',
      align: 'center',
      width: '3%',
      render: (row) => <span className="num">{row._idx + 1}</span>,
    },
    {
      key: 'codeTitle',
      header: 'Наименование',
      width: '17%',
      render: (row) => (
        <>
          <span className="parent-tag">{row.code}</span>
          <span className="zname">{row.title}</span>
        </>
      ),
    },
    {
      key: 'mtr',
      header: 'Тип МТР',
      width: '8%',
      render: (row) => row.mtr ?? '—',
    },
    {
      key: 'tender_num',
      header: '№ заявки',
      width: '7%',
      render: (row) => (
        <span className="zaglink">{row.tender_num ?? '—'}</span>
      ),
    },
    {
      key: 'proc',
      header: '№ процедуры',
      width: '8%',
      render: (row) => <span className="proc-id">{row.proc ?? '—'}</span>,
    },
    {
      key: 'supplier',
      header: 'Поставщик',
      width: '14%',
      render: (row) =>
        row.supplier ? (
          <span className="supp-c">{row.supplier}</span>
        ) : (
          <span className="supp-c empty">не выбран</span>
        ),
    },
    {
      key: 'zagruzka',
      header: 'Дата загрузки',
      width: '9%',
      render: (row) => <span className="dt">{dateRu(row.zagruzka)}</span>,
    },
    {
      key: 'pub_start',
      header: 'Нач. публ.',
      width: '9%',
      render: (row) => <span className="dt">{dateRu(row.pub_start)}</span>,
    },
    {
      key: 'pub_end',
      header: 'Заверш. публ.',
      width: '9%',
      render: (row) => <span className="dt">{dateRu(row.pub_end)}</span>,
    },
    {
      key: 'position_count',
      header: 'Поз.',
      align: 'center',
      width: '5%',
      render: (row) => <span className="posc">{row.position_count}</span>,
    },
    {
      key: 'status_zakup',
      header: 'Статус',
      width: '11%',
      render: (row) => {
        // Read-only users see the chip. Editors get an inline <select> that
        // PATCHes status_zakup directly from the row.
        if (!canEdit) {
          const { kind, label } = procStatusChip(row.status_zakup)
          return <Chip kind={kind} label={label} mini />
        }
        const opts = statusOptions ?? []
        const current = row.status_zakup
        const inOpts = current != null && opts.includes(current)
        // Color the select by the current status (matches the read-only chip).
        const kind = procStatusChip(current).kind
        return (
          <select
            value={inOpts ? current : ''}
            // Stop propagation so opening/changing the dropdown does NOT fire
            // the row's onRowClick (which navigates to the card).
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => {
              const v = e.target.value
              if (v && v !== current) onStatusChange(row.id, v)
            }}
            title={current ?? '—'}
            style={{
              width: '100%',
              padding: '3px 8px',
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 5,
              border: 'none',
              cursor: 'pointer',
              ...STATUS_KIND_COLOR[kind],
            }}
          >
            {/* Current status not in the dict (Новая / null / Отменена): show
                it as a disabled placeholder so the value is visible but the
                user can only pick a real справочник value. */}
            {!inOpts && (
              <option value="" disabled>
                {current ?? '—'}
              </option>
            )}
            {opts.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        )
      },
    },
  ]
}

// ---- Page -----------------------------------------------------------------

export function Zakupka() {
  const navigate = useNavigate()
  const { permissions } = useAuth()
  const canEditZakup = canEdit(permissions, 'zakupka')
  const qc = useQueryClient()

  // Status dictionary for the inline row <select> (6 purchasable values).
  const statusDict = useQuery({
    queryKey: ['dict', 'status_zakup'],
    queryFn: () => listDict('status_zakup'),
  })

  // Change status_zakup directly from a list row. Optimistic-enough: the list
  // refetches on success, so the select (controlled by row.status_zakup) updates.
  const statusMut = useMutation({
    mutationFn: (vars: { id: number; status: string }) =>
      patchProcedure(vars.id, { status_zakup: vars.status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['procurements'] }),
    onError: (err) => console.error('status patch failed', err),
  })
  const onStatusChange = useCallback(
    (id: number, status: string) => statusMut.mutate({ id, status }),
    [statusMut],
  )

  const [searchInput, setSearchInput] = useState('')
  const [nonSearch, setNonSearch] = useState<SortAndArchive>(DEFAULT_NON_SEARCH)

  const debouncedSearch = useDebounced(searchInput, 300)

  const query = useQuery({
    queryKey: [
      'procurements',
      { search: debouncedSearch, ...nonSearch },
    ],
    queryFn: () =>
      listProcurements({
        search: debouncedSearch || undefined,
        include_archived: nonSearch.include_archived || undefined,
        sort: nonSearch.sort,
        page: 1,
        page_size: 100,
      }),
  })

  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const total = query.data?.total ?? 0
  const columns = useMemo(
    () =>
      buildColumns({
        statusOptions: statusDict.data?.map((d) => d.value) ?? null,
        onStatusChange,
        canEdit: canEditZakup,
      }),
    [statusDict.data, onStatusChange, canEditZakup],
  )

  const numbered: NumberedProc[] = useMemo(
    () => items.map((r, i) => ({ ...r, _idx: i })),
    [items],
  )

  const hasFilterApplied =
    debouncedSearch.trim() !== '' || nonSearch.include_archived

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>В закупке</h1>
        <span className="desc">
          взяты в работу закупщиками · идут торги на ЭТП
        </span>
        <span className="sp" />
      </div>

      <FilterBar
        actions={
          canEditZakup ? (
            <button
              className="badd"
              disabled
              title="В разработке"
            >
              + Заявка
            </button>
          ) : null
        }
      >
        <input
          type="text"
          className="rep-sel"
          style={{ minWidth: 220 }}
          placeholder="Поиск по коду, № заявки, поставщику…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          className="rep-sel"
          value={nonSearch.sort}
          onChange={(e) =>
            setNonSearch((s) => ({
              ...s,
              sort: e.target.value as ProcedureSort,
            }))
          }
        >
          <option value="created_at">По дате создания</option>
          <option value="code">По коду</option>
          <option value="num">По № заявки</option>
          <option value="proc">По № процедуры</option>
          <option value="supplier">По поставщику</option>
          <option value="status">По статусу</option>
          <option value="mtr">По типу МТР</option>
          <option value="zagruzka">По дате загрузки</option>
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
              setNonSearch((s) => ({
                ...s,
                include_archived: e.target.checked,
              }))
            }
          />
          Показать отменённые
        </label>
      </FilterBar>

      <div className="block" style={{ '--bc': 'var(--proc)' } as CSSProperties}>
        <div className="block-h">
          <span className="bnum">2</span>
          <div>
            <div className="btitle">В закупке</div>
            <div className="beng">In procurement</div>
          </div>
          <span className="bcount">
            {total} {pluralRequests(total)}
          </span>
          <span className="sp" />
          <button className="bexport" type="button">
            ↧ Экспорт
          </button>
        </div>
        <div className="tbl-scroll">
          {query.isLoading ? (
            <div className="empty-state">Загрузка…</div>
          ) : query.isError ? (
            <EmptyState
              title="Ошибка загрузки"
              hint={String(
                (query.error as { body?: { detail?: string } })?.body
                  ?.detail ?? query.error,
              )}
            />
          ) : (
            <DataTable<NumberedProc>
              columns={columns}
              rows={numbered}
              getRowId={(r) => r.id}
              onRowClick={(row) => navigate(`/zakupka/${row.id}`)}
              empty={
                <EmptyState
                  title={hasFilterApplied ? 'Ничего не найдено' : 'Нет процедур'}
                  hint={
                    hasFilterApplied
                      ? undefined
                      : 'Заявки появляются здесь после «Взять в работу».'
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
