import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ColumnDef } from '../components/types'
import { Chip } from '../components/Chip'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ExcelTable } from '../components/ExcelTable'
import { FilterBar } from '../components/FilterBar'
import { Modal } from '../components/Modal'
import {
  createRequest,
  listRequests,
  type RequestCreate,
  type RequestListItem,
  type RequestPositionInput,
  type RequestSort,
} from '../api/requests'
import { useAuth } from '../auth/AuthContext'
import { canEdit } from '../lib/permissions'
import { dateRu } from '../lib/format'
import { pluralRequests } from '../lib/plural'

type SortAndArchive = {
  include_archived: boolean
  sort: RequestSort
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

// ---- Request column definitions -------------------------------------------

// `_idx` carries the row's position in the displayed list (1-based index for
// the `#` column). The DataTable render callback receives a single row, so we
// pre-number rows before handing them to the table.
type NumberedRow = RequestListItem & { _idx: number }

function buildColumns(): DataTableColumn<NumberedRow>[] {
  return [
    {
      key: '_idx',
      header: '#',
      align: 'center',
      render: (row) => <span className="num">{row._idx + 1}</span>,
    },
    {
      key: 'codeTitle',
      header: 'Наименование',
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
      render: (row) => row.mtr ?? '—',
    },
    {
      key: 'srok',
      header: 'Срок',
      render: (row) => <span className="dt">{dateRu(row.srok)}</span>,
    },
    {
      key: 'zagruzka',
      header: 'Дата загрузки',
      render: (row) => <span className="dt">{dateRu(row.zagruzka)}</span>,
    },
    {
      key: 'sostavitel',
      header: 'Составитель',
      render: (row) => row.sostavitel,
    },
    {
      key: 'position_count',
      header: 'Поз.',
      align: 'center',
      render: (row) => <span className="posc">{row.position_count}</span>,
    },
    {
      key: 'status',
      header: 'Статус',
      render: (row) => (
        <Chip
          kind={row.status === 'cancelled' ? 'cancel' : 'wait'}
          label={row.status === 'cancelled' ? 'Отменена' : 'Ожидают закупки'}
          mini
        />
      ),
    },
  ]
}

// ---- Create modal ---------------------------------------------------------

type DraftRow = {
  id: string
  name: string | null
  qty: number | null
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
}

function makeDraftRow(): DraftRow {
  return {
    id:
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `r-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: null,
    qty: null,
    unit: null,
    gost_tu: null,
    doc_code: null,
  }
}

const DRAFT_COLUMNS: ColumnDef<DraftRow>[] = [
  { key: 'name', header: 'Наименование', type: 'text', width: 'minmax(220px, 3fr)' },
  { key: 'qty', header: 'Кол-во', type: 'number', width: 'minmax(90px, 1fr)', align: 'right' },
  { key: 'unit', header: 'Ед. изм.', type: 'text', width: 'minmax(80px, 1fr)' },
  { key: 'gost_tu', header: 'ГОСТ/ТУ', type: 'text', width: 'minmax(120px, 1fr)' },
  { key: 'doc_code', header: 'Шифр документации', type: 'text', width: 'minmax(140px, 1fr)' },
]

const fieldStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 5,
}

const labelStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
}

function CreateRequestModal({
  onClose,
}: {
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [mtr, setMtr] = useState('')
  const [srok, setSrok] = useState('')
  const [dept, setDept] = useState('')
  const [rows, setRows] = useState<DraftRow[]>(() => [makeDraftRow()])
  const [submitErr, setSubmitErr] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: (payload: RequestCreate) => createRequest(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['requests'] })
      onClose()
    },
    onError: (err: unknown) => {
      const apiErr = err as { status?: number; body?: { detail?: string } }
      const detail = apiErr?.body?.detail
      setSubmitErr(
        apiErr?.status === 409
          ? 'Заявка с таким кодом уже существует'
          : detail ?? 'Не удалось создать заявку',
      )
    },
  })

  const positions: RequestPositionInput[] = useMemo(
    () =>
      rows
        .filter((r) => (r.name ?? '').trim() !== '' && r.qty != null)
        .map((r) => ({
          name: (r.name ?? '').trim(),
          qty: Number(r.qty),
          unit: r.unit ?? null,
          gost_tu: r.gost_tu ?? null,
          doc_code: r.doc_code ?? null,
        })),
    [rows],
  )

  const canSubmit =
    code.trim() !== '' && title.trim() !== '' && positions.length > 0

  function onSubmit() {
    if (!canSubmit) return
    setSubmitErr(null)
    createMut.mutate({
      code: code.trim(),
      title: title.trim(),
      mtr: mtr.trim() || null,
      srok: srok || null,
      dept: dept.trim() || null,
      positions,
    })
  }

  function onRowsChange(next: DraftRow[]) {
    if (next.length === 0) {
      setRows([makeDraftRow()])
      return
    }
    setRows(next)
  }

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Новая заявка"
      width={760}
      footer={
        <>
          <span className="sp" />
          <button className="btn ghost" onClick={onClose} disabled={createMut.isPending}>
            Отмена
          </button>
          <button
            className="btn primary"
            onClick={onSubmit}
            disabled={!canSubmit || createMut.isPending}
          >
            {createMut.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label style={fieldStyle}>
          <span style={labelStyle}>Код *</span>
          <input
            type="text"
            className="rep-sel"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Т-67"
            required
          />
        </label>
        <label style={fieldStyle}>
          <span style={labelStyle}>Наименование *</span>
          <input
            type="text"
            className="rep-sel"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Трубопроводный узел №3"
            required
          />
        </label>
        <label style={fieldStyle}>
          <span style={labelStyle}>Тип МТР</span>
          <input
            type="text"
            className="rep-sel"
            value={mtr}
            onChange={(e) => setMtr(e.target.value)}
            placeholder="Трубная продукция"
          />
        </label>
        <label style={fieldStyle}>
          <span style={labelStyle}>Срок</span>
          <input
            type="date"
            className="rep-sel"
            value={srok}
            onChange={(e) => setSrok(e.target.value)}
          />
        </label>
        <label style={{ ...fieldStyle, gridColumn: '1 / -1' }}>
          <span style={labelStyle}>Подразделение</span>
          <input
            type="text"
            className="rep-sel"
            value={dept}
            onChange={(e) => setDept(e.target.value)}
            placeholder="Комплектация-1"
          />
        </label>
      </div>

      <div style={{ marginTop: 16 }}>
        <div style={labelStyle}>Позиции *</div>
        <ExcelTable
          rows={rows}
          columns={DRAFT_COLUMNS}
          getRowId={(r) => r.id}
          onRowsChange={onRowsChange}
          emptyMessage="Вставьте строки из Excel или добавьте вручную"
        />
        <div style={{ marginTop: 6, fontSize: 11, color: 'var(--muted)' }}>
          Вставьте данные из Excel/Sheets (Ctrl+V) — колонки заполнятся автоматически.
        </div>
      </div>

      {submitErr && (
        <div
          style={{
            marginTop: 12,
            padding: '8px 10px',
            fontSize: 12,
            color: 'var(--late)',
            background: 'var(--late-bg)',
            borderRadius: 5,
          }}
        >
          {submitErr}
        </div>
      )}
    </Modal>
  )
}

// ---- Page -----------------------------------------------------------------

export function Komplektaciya() {
  const navigate = useNavigate()
  const { permissions } = useAuth()
  const canEditKomp = canEdit(permissions, 'komplektaciya')

  const [searchInput, setSearchInput] = useState('')
  const [nonSearch, setNonSearch] = useState<SortAndArchive>(DEFAULT_NON_SEARCH)
  // Counter that ticks on each open/close of the create modal. Bumping it
  // remounts the modal so its internal state (form fields, draft rows)
  // resets to initial values — no setState-in-effect needed.
  const [createOpenNonce, setCreateOpenNonce] = useState(0)

  const debouncedSearch = useDebounced(searchInput, 300)

  const query = useQuery({
    queryKey: ['requests', { search: debouncedSearch, ...nonSearch }],
    queryFn: () =>
      listRequests({
        search: debouncedSearch || undefined,
        include_archived: nonSearch.include_archived || undefined,
        sort: nonSearch.sort,
        page: 1,
        page_size: 100,
      }),
  })

  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const total = query.data?.total ?? 0
  const columns = useMemo(() => buildColumns(), [])

  const numbered: NumberedRow[] = useMemo(
    () => items.map((r, i) => ({ ...r, _idx: i })),
    [items],
  )

  const hasFilterApplied =
    debouncedSearch.trim() !== '' || nonSearch.include_archived

  return (
    <div className="wrap">
      <div className="page-h">
        <h1>Комплектация</h1>
        <span className="desc">
          заявки, загруженные комплектовщиками — ожидают закупки
        </span>
        <span className="sp" />
      </div>

      <FilterBar
        actions={
          canEditKomp ? (
            <button
              className="badd"
              onClick={() => setCreateOpenNonce((n) => n + 1)}
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
          placeholder="Поиск по коду или наименованию…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          className="rep-sel"
          value={nonSearch.sort}
          onChange={(e) =>
            setNonSearch((s) => ({ ...s, sort: e.target.value as RequestSort }))
          }
        >
          <option value="created_at">По дате создания</option>
          <option value="code">По коду</option>
          <option value="title">По наименованию</option>
        </select>
        <label
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}
        >
          <input
            type="checkbox"
            checked={nonSearch.include_archived}
            onChange={(e) =>
              setNonSearch((s) => ({ ...s, include_archived: e.target.checked }))
            }
          />
          Показать отменённые
        </label>
      </FilterBar>

      <div className="block" style={{ '--bc': 'var(--wait)' } as CSSProperties}>
        <div className="block-h">
          <span className="bnum">1</span>
          <div>
            <div className="btitle">Ожидают закупки</div>
            <div className="beng">Awaiting procurement</div>
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
                (query.error as { body?: { detail?: string } })?.body?.detail ??
                  query.error,
              )}
            />
          ) : (
            <DataTable<NumberedRow>
              columns={columns}
              rows={numbered}
              getRowId={(r) => r.id}
              onRowClick={(row) => navigate(`/komplektaciya/${row.id}`)}
              empty={
                <EmptyState
                  title={hasFilterApplied ? 'Ничего не найдено' : 'Нет заявок'}
                  hint={
                    hasFilterApplied
                      ? undefined
                      : 'Нажмите «+ Заявка», чтобы создать первую заявку.'
                  }
                />
              }
            />
          )}
        </div>
      </div>

      {createOpenNonce > 0 && (
        <CreateRequestModal
          key={createOpenNonce}
          onClose={() => setCreateOpenNonce(0)}
        />
      )}
    </div>
  )
}
