import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import {
  PositionTable,
  type PositionTableColumn,
} from '../components/PositionTable'
import { Modal } from '../components/Modal'
import { StatusSelect } from '../components/StatusSelect'
import { useAuth } from '../auth/AuthContext'
import {
  addProcedurePositions,
  cancelProcedure,
  deleteProcedurePosition,
  getProcedure,
  patchProcedure,
  patchProcedurePosition,
  splitProcedure,
  toSupport,
  uncancelProcedure,
  type ProcedureDetail,
  type ProcedurePatch,
  type ProcedurePosition,
  type ProcedurePositionInput,
  type ProcedurePositionPatch,
  type SplitPayload,
} from '../api/procedures'
import { getRequest, type ProcedureOut } from '../api/requests'
import { listDict, type DictValue } from '../api/dict'
import { procStatusChip } from '../lib/statusColors'
import { dateRu, money } from '../lib/format'
import { canEdit } from '../lib/permissions'
import { kopecksToRublesInput, rublesToKopecks } from '../lib/money'

// ---- Pure helpers ---------------------------------------------------------

/**
 * Sum qty*price across positions (price is INTEGER kopecks, nullable).
 * A null price contributes 0. Exported for unit testing.
 */
export function sumPositionsKopecks(
  positions: { qty: number; price: number | null }[],
): number {
  let sum = 0
  for (const p of positions) {
    sum += p.qty * (p.price ?? 0)
  }
  return sum
}

function lastErrorMessage(err: unknown): string {
  const apiErr = err as { body?: { detail?: string } }
  return apiErr?.body?.detail ?? 'Не удалось выполнить действие'
}

// ---- Editable position row ------------------------------------------------

type EditableRow = {
  _localId: string
  id?: number
  name: string | null
  qty: string | null
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
  price: string | null // rubles string (kopecks↔rubles via money.ts)
  _num?: string // display-only 1-based ordinal for the «№» column (not persisted)
}

function makeLocalRow(): EditableRow {
  return {
    _localId:
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: null,
    qty: null,
    unit: null,
    gost_tu: null,
    doc_code: null,
    price: null,
  }
}

function toEditable(p: ProcedurePosition): EditableRow {
  return {
    _localId: `pos-${p.id}`,
    id: p.id,
    name: p.name,
    qty: p.qty == null ? null : String(p.qty),
    unit: p.unit,
    gost_tu: p.gost_tu,
    doc_code: p.doc_code,
    price: kopecksToRublesInput(p.price),
  }
}

// ---- Editable header draft ------------------------------------------------

type HeaderDraft = {
  tender_num: string
  proc: string
  supplier: string
  fio_zakupshchik: string
  pub_start: string
  pub_end: string
  status_zakup: string
}

function headerFromProc(p: ProcedureDetail): HeaderDraft {
  return {
    tender_num: p.tender_num ?? '',
    proc: p.proc ?? '',
    supplier: p.supplier ?? '',
    fio_zakupshchik: p.fio_zakupshchik ?? '',
    pub_start: p.pub_start ?? '',
    pub_end: p.pub_end ?? '',
    status_zakup: p.status_zakup ?? '',
  }
}

// ---- Split dialog local state --------------------------------------------

type SplitEntry = { source_position_id: number; name: string; available: number; qty: string }

// ---- Component ------------------------------------------------------------

export function ProcedureCard() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const procedureId = id ? Number(id) : NaN
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const editable = canEdit(permissions, 'zakupka')

  const query = useQuery({
    queryKey: ['procedure', procedureId],
    queryFn: () => getProcedure(procedureId),
    enabled: Number.isFinite(procedureId),
  })

  const proc = query.data

  // Status dictionary for the header <select> (6 purchasable values).
  const statusDict = useQuery({
    queryKey: ['dict', 'status_zakup'],
    queryFn: () => listDict('status_zakup'),
  })

  // Sister data: the tender's procedures, fetched via the parent request.
  const sisterQuery = useQuery({
    queryKey: ['request', proc?.parent_id],
    queryFn: () => getRequest(proc!.parent_id),
    enabled: !!proc,
  })

  // Derive sisters: find the tender that owns this procedure in the parent's
  // tenders, then take its procedures. Falls back to [] if anything is off.
  const sisters = useMemo<ProcedureOut[]>(() => {
    if (!proc || !sisterQuery.data) return []
    const tender = sisterQuery.data.tenders.find(
      (t) => t.id === proc.tender_id,
    )
    return tender?.procedures ?? []
  }, [proc, sisterQuery.data])

  // ---- Editable local state (mirrors RequestCard) ------------------------
  const [headerDraft, setHeaderDraft] = useState<HeaderDraft | null>(null)
  const [editRows, setEditRows] = useState<EditableRow[] | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)
  const [savedTick, setSavedTick] = useState(0)
  const [splitOpen, setSplitOpen] = useState(false)
  // Pending flag for the unified save (header + positions together) — disables
  // the save button during the request, preventing double-submit.
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (savedTick === 0) return
    const t = window.setTimeout(() => setSavedTick(0), 2500)
    return () => window.clearTimeout(t)
  }, [savedTick])

  // When the route param changes (sister-switcher navigation), reset the local
  // drafts so they re-seed from the NEW procedure. Without this the card keeps
  // the PREVIOUS procedure's positions + header after switching sisters.
  useEffect(() => {
    setHeaderDraft(null)
    setEditRows(null)
    setActionErr(null)
  }, [procedureId])

  // Can the user edit THIS procedure? Editable only in the zakupka block and
  // only when NOT cancelled. (`editable` gates the permission; this gate also
  // reflects per-row state.)
  const isCancelled = proc?.status_zakup === 'Отменена'
  const canEditThis =
    editable && !!proc && proc.block === 'zakupka' && !isCancelled

  // Seed local drafts from server data (only if user can edit and the proc is
  // in the editable state). We check `=== null` so subsequent user edits are
  // never stomped.
  if (proc && headerDraft === null && canEditThis) {
    setHeaderDraft(headerFromProc(proc))
  }
  if (proc && editRows === null && canEditThis) {
    setEditRows(proc.positions.map(toEditable))
  }

  async function refresh() {
    // Await the card refetch BEFORE resetting the local drafts. The drafts are
    // re-seeded during render from query.data; if we only invalidate, the
    // re-seed reads a PRE-save snapshot and the next save reverts the change
    // (pitfall #2). Awaiting guarantees the re-seed reads fresh data.
    await qc.refetchQueries({ queryKey: ['procedure', procedureId] })
    qc.invalidateQueries({ queryKey: ['procurements'] })
    // The sister-switcher reads the parent request's procedures. A split adds a
    // new sister procedure to the tender, so invalidate the parent-request
    // query too — otherwise the new sister chip stays missing until a full
    // reload. Fire-and-forget (the chip appears when the refetch lands).
    if (proc?.parent_id) {
      qc.invalidateQueries({ queryKey: ['request', proc.parent_id] })
    }
    setHeaderDraft(null)
    setEditRows(null)
  }

  // ---- Mutations ----------------------------------------------------------

  const cancelMut = useMutation({
    mutationFn: () => cancelProcedure(procedureId),
    onSuccess: () => refresh(),
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const uncancelMut = useMutation({
    mutationFn: () => uncancelProcedure(procedureId),
    onSuccess: () => refresh(),
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const toSupportMut = useMutation({
    mutationFn: () => toSupport(procedureId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['procurements'] })
      navigate('/zakupka')
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const splitMut = useMutation({
    mutationFn: (payload: SplitPayload) => splitProcedure(procedureId, payload),
    onSuccess: async () => {
      await refresh()
      setSplitOpen(false)
      setSavedTick((t) => t + 1)
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  // ---- Header diff (used by the unified saveAll) -------------------------

  // Build a ProcedurePatch of only the header fields that changed vs the
  // server. Empty object = nothing to save.
  function buildHeaderPatch(draft: HeaderDraft): ProcedurePatch {
    if (!proc) return {}
    const patch: ProcedurePatch = {}
    if (draft.tender_num !== (proc.tender_num ?? ''))
      patch.tender_num = draft.tender_num.trim() || null
    if (draft.proc !== (proc.proc ?? ''))
      patch.proc = draft.proc.trim() || null
    if (draft.supplier !== (proc.supplier ?? ''))
      patch.supplier = draft.supplier.trim() || null
    if (draft.fio_zakupshchik !== (proc.fio_zakupshchik ?? ''))
      patch.fio_zakupshchik = draft.fio_zakupshchik.trim() || null
    if (draft.pub_start !== (proc.pub_start ?? ''))
      patch.pub_start = draft.pub_start.trim() || null
    if (draft.pub_end !== (proc.pub_end ?? ''))
      patch.pub_end = draft.pub_end.trim() || null
    if (draft.status_zakup !== (proc.status_zakup ?? ''))
      patch.status_zakup = draft.status_zakup.trim() || null
    return patch
  }

  // ---- Position editing ---------------------------------------------------
  //
  // PositionTable wiring — controlled by the parent editRows state. Deleted
  // rows are dropped from editRows; savePositions diff editRows vs the server
  // positions to issue the DELETEs (pitfall #1: NO side-effects in updaters).

  const onCellChange = useCallback(
    (rowId: string | number, key: string, value: string | null) => {
      setEditRows((prev) => {
        const cur = prev ?? []
        return cur.map((r) =>
          r._localId === rowId
            ? { ...r, [key]: value === null || value === '' ? null : value }
            : r,
        )
      })
    },
    [],
  )

  const onDeleteRow = useCallback((rowId: string | number) => {
    setEditRows((prev) => {
      const cur = prev ?? []
      const next = cur.filter((r) => r._localId !== rowId)
      return next.length === 0 ? [makeLocalRow()] : next
    })
  }, [])

  const onAddRows = useCallback(
    (afterRowId: string | number | null, count: number): string[] => {
      const fresh: EditableRow[] = []
      const newIds: string[] = []
      for (let i = 0; i < count; i++) {
        const newRow = makeLocalRow()
        fresh.push(newRow)
        newIds.push(newRow._localId)
      }
      setEditRows((prev) => {
        const cur = prev ?? []
        const idx =
          afterRowId === null
            ? cur.length
            : cur.findIndex((r) => r._localId === afterRowId)
        const insertAt = idx === -1 ? cur.length : idx + 1
        return [...cur.slice(0, insertAt), ...fresh, ...cur.slice(insertAt)]
      })
      return newIds
    },
    [],
  )

  const positionColumns = useMemo<PositionTableColumn<EditableRow>[]>(
    () => [
      // Display-only 1-based ordinal (the «№» column, like Комплектация).
      // ProcedurePosition has no persisted num, so this is computed from the
      // row index (see `tableRows`) and is read-only.
      { key: '_num', header: '№', width: '44px', align: 'center', mono: true, readOnly: true },
      { key: 'name', header: 'Наименование', width: 'minmax(180px, 1fr)' },
      { key: 'qty', header: 'Кол-во', width: '90px', align: 'right', mono: true },
      { key: 'unit', header: 'Ед. изм.', width: '80px', mono: true },
      { key: 'gost_tu', header: 'ГОСТ/ТУ', width: '140px' },
      { key: 'doc_code', header: 'Шифр документации', width: '180px' },
      {
        key: 'price',
        header: 'Цена',
        width: '120px',
        align: 'right',
        mono: true,
        // editRows.price is a RUBLES string the user may type with a comma
        // decimal (ru-RU). Normalize ',' -> '.' before parsing, and fall back
        // to '—' for non-finite input so a malformed entry never renders
        // "NaN ₽". Save still validates via rublesToKopecks.
        format: (v) => {
          if (!v) return '—'
          const k = Math.round(Number(String(v).replace(',', '.')) * 100)
          return Number.isFinite(k) ? money(k) : '—'
        },
      },
    ],
    [],
  )

  // Unified save: persists BOTH header changes and position changes in one
  // action. There is a single «Сохранить изменения» button (actbar) so editing
  // the header then saving positions (or vice versa) never silently drops the
  // other section's unsaved edits — the prior two-button design did (e.g. ФИО
  // закупщика vanished when the positions save reset the header draft).
  async function saveAll() {
    if (!proc) return
    if (saving) return
    setActionErr(null)
    setSaving(true)
    try {
      // 1. Header (only if a field changed).
      if (headerDraft) {
        const patch = buildHeaderPatch(headerDraft)
        if (Object.keys(patch).length > 0) {
          await patchProcedure(procedureId, patch)
        }
      }
      // 2. Positions (only if editable rows exist).
      if (editRows) {
        const original = proc.positions
        // 2a. Patch each existing row that changed.
        for (const row of editRows) {
          if (row.id === undefined) continue
          const prev = original.find((p) => p.id === row.id)
          if (!prev) continue
          const patch: ProcedurePositionPatch = {}
          if ((row.name ?? '') !== prev.name) patch.name = row.name ?? ''
          // Guard against non-numeric qty: a malformed string like 'abc' would
          // otherwise coerce to NaN -> JSON null -> backend nulls the column
          // (silent data corruption). Only patch qty when it is finite.
          const rowQty = Number(row.qty)
          if (Number.isFinite(rowQty) && rowQty !== Number(prev.qty))
            patch.qty = rowQty
          if ((row.unit ?? null) !== (prev.unit ?? null)) patch.unit = row.unit ?? null
          if ((row.gost_tu ?? null) !== (prev.gost_tu ?? null)) patch.gost_tu = row.gost_tu ?? null
          if ((row.doc_code ?? null) !== (prev.doc_code ?? null)) patch.doc_code = row.doc_code ?? null
          const prevPriceKop = rublesToKopecks(kopecksToRublesInput(prev.price))
          const rowPriceKop = rublesToKopecks(row.price)
          if (rowPriceKop !== prevPriceKop) patch.price = rowPriceKop
          if (Object.keys(patch).length > 0) {
            await patchProcedurePosition(procedureId, row.id, patch)
          }
        }
        // 2b. Mass-insert new (id-less) rows that have name+qty.
        const newRows: ProcedurePositionInput[] = editRows
          .filter(
            (r) =>
              r.id === undefined &&
              (r.name ?? '').trim() !== '' &&
              r.qty != null &&
              (r.qty ?? '').trim() !== '',
          )
          .map((r) => ({
            name: (r.name ?? '').trim(),
            qty: Number(r.qty),
            unit: r.unit ?? null,
            gost_tu: r.gost_tu ?? null,
            doc_code: r.doc_code ?? null,
            price: rublesToKopecks(r.price),
          }))
        if (newRows.length > 0) {
          await addProcedurePositions(procedureId, newRows)
        }
        // 2c. Delete positions removed by the user — diff editRows vs original.
        const currentIds = new Set(
          editRows.filter((r) => r.id !== undefined).map((r) => r.id as number),
        )
        for (const p of original) {
          if (!currentIds.has(p.id)) {
            await deleteProcedurePosition(procedureId, p.id)
          }
        }
      }
      await refresh()
      setSavedTick((t) => t + 1)
    } catch (err) {
      setActionErr(lastErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  // ---- Total --------------------------------------------------------------
  //
  // Compute from editRows when present (qty=Number(r.qty), price=kopecks),
  // else from the server positions. sumPositionsKopecks is exported.
  const total = useMemo(() => {
    if (editRows) {
      return sumPositionsKopecks(
        editRows.map((r) => ({
          qty: Number(r.qty) || 0,
          price: rublesToKopecks(r.price),
        })),
      )
    }
    return proc ? sumPositionsKopecks(proc.positions) : 0
  }, [editRows, proc])

  // Rows handed to PositionTable, with a 1-based «№» ordinal attached. Derived
  // from editRows (when editing) or the server positions; recomputed on every
  // edit so the numbering stays in sync after add / delete / reorder.
  const tableRows = useMemo<EditableRow[]>(() => {
    const base = editRows ?? (proc ? proc.positions.map(toEditable) : [])
    return base.map((r, i) => ({ ...r, _num: String(i + 1) }))
  }, [editRows, proc])

  // ---- Early returns (mirror RequestCard states) -------------------------

  if (!Number.isFinite(procedureId)) {
    return (
      <div className="wrap">
        <button className="back" onClick={() => navigate('/zakupka')}>
          ‹ Назад
        </button>
        <EmptyState title="Некорректный идентификатор процедуры" />
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <div className="wrap">
        <button className="back" onClick={() => navigate('/zakupka')}>
          ‹ Назад
        </button>
        <div className="empty-state">Загрузка…</div>
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="wrap">
        <button className="back" onClick={() => navigate('/zakupka')}>
          ‹ Назад
        </button>
        <EmptyState title="Ошибка загрузки" hint={lastErrorMessage(query.error)} />
      </div>
    )
  }

  if (!proc) return null

  const status = procStatusChip(proc.status_zakup)
  const onSupport = proc.status_zakup === 'На сделку'
  const rowCount = (editRows ?? proc.positions.map(toEditable)).filter(
    (r) => r.id !== undefined || (r.name ?? '').trim() !== '',
  ).length
  const showCount = editRows ? rowCount : proc.positions.length

  // ---- Split dialog state (built fresh on each open via key) -------------

  function openSplit() {
    setActionErr(null)
    setSplitOpen(true)
  }

  return (
    <div className="wrap">
      <button className="back" onClick={() => navigate('/zakupka')}>
        ‹ Назад
      </button>

      <div className="dcard">
        <div className="dhead">
          <div className="crumbs">
            <span className="pcode">{proc.code}</span>
            {sisters.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`sib${s.id === procedureId ? ' on' : ''}`}
                onClick={() => navigate(`/zakupka/${s.id}`)}
              >
                {s.proc ?? `#${s.id}`}
              </button>
            ))}
            <span className="sp" />
            <Chip kind={status.kind} label={status.label} mini />
          </div>
          <div className="top">
            <div style={{ flex: 1, minWidth: 280 }}>
              <h1>
                {proc.code}
                <small>{proc.title}</small>
              </h1>
              {canEditThis && headerDraft ? (
                <HeaderEditPanel
                  draft={headerDraft}
                  statusOptions={statusDict.data ?? null}
                  onChange={(key, value) =>
                    setHeaderDraft((prev) =>
                      prev ? { ...prev, [key]: value } : prev,
                    )
                  }
                  disabled={saving}
                />
              ) : (
                <>
                  <div className="mt">
                    <b>№ заявки:</b> {proc.tender_num ?? '—'} ·{' '}
                    <b>№ процедуры:</b> {proc.proc ?? '—'} ·{' '}
                    <b>Поставщик:</b>{' '}
                    {proc.supplier ?? (
                      <span className="supp-c empty">не выбран</span>
                    )}{' '}
                    · <b>Тип МТР:</b> {proc.mtr ?? '—'} ·{' '}
                    <b>Закупщик:</b> {proc.fio_zakupshchik ?? '—'}
                  </div>
                  <div className="mt">
                    <b>Нач. публ.:</b> {dateRu(proc.pub_start)} ·{' '}
                    <b>Заверш. публ.:</b> {dateRu(proc.pub_end)} ·{' '}
                    <b>Дата загрузки:</b> {dateRu(proc.zagruzka)} ·{' '}
                    <b>Сумма:</b> {money(total)}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="actbar">
          <span className="z">
            Позиций: <b>{showCount}</b>
          </span>
          <span className="sp" />
          {canEditThis && (
            <>
              <button
                className="btn"
                onClick={openSplit}
                disabled={proc.positions.length === 0}
              >
                Разбить по поставщикам
              </button>
              <button
                className="btn"
                onClick={() => cancelMut.mutate()}
                disabled={cancelMut.isPending}
              >
                Отменить
              </button>
              <button
                className="btn primary"
                onClick={saveAll}
                disabled={saving}
              >
                {saving ? 'Сохранение…' : 'Сохранить изменения'}
              </button>
            </>
          )}
          {isCancelled && editable && proc.block === 'zakupka' && (
            <button
              className="btn"
              onClick={() => uncancelMut.mutate()}
              disabled={uncancelMut.isPending}
            >
              Вернуть из отмены
            </button>
          )}
          {editable && proc.block === 'zakupka' && (
            <button
              className="btn primary"
              onClick={() => toSupportMut.mutate()}
              disabled={!onSupport || toSupportMut.isPending}
              title={
                onSupport
                  ? undefined
                  : 'Доступно только со статусом «На сделку»'
              }
            >
              {toSupportMut.isPending ? 'Передача…' : 'Передать в сопровождение'}
            </button>
          )}
        </div>

        {actionErr && (
          <div
            style={{
              margin: '14px 22px 0',
              padding: '8px 10px',
              fontSize: 12,
              color: 'var(--late)',
              background: 'var(--late-bg)',
              borderRadius: 5,
            }}
          >
            {actionErr}
          </div>
        )}

        {savedTick > 0 && (
          <div
            style={{
              margin: '14px 22px 0',
              padding: '8px 12px',
              fontSize: 12.5,
              fontWeight: 500,
              color: 'var(--ok)',
              background: 'var(--ok-bg)',
              borderRadius: 5,
            }}
          >
            ✓ Изменения сохранены
          </div>
        )}

        <div style={{ padding: '14px 22px' }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--faint)',
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            Позиции процедуры
          </div>
          <PositionTable<EditableRow>
            rows={tableRows}
            columns={positionColumns}
            getRowId={(r) => r._localId}
            onCellChange={onCellChange}
            onDeleteRow={onDeleteRow}
            onAddRows={onAddRows}
            readOnly={!canEditThis}
            showRowNumber={false}
            emptyMessage="Нет позиций"
          />
          <div style={{ marginTop: 8, fontSize: 12.5, color: 'var(--faint)' }}>
            Сумма: <b>{money(total)}</b>
          </div>
        </div>

        <div style={{ padding: '14px 22px' }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--faint)',
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            Комментарии
          </div>
          <EmptyState
            title="Комментариев пока нет"
            hint="Лента комментариев появится в Фазе 10."
          />
        </div>

        <div style={{ padding: '0 22px 22px' }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--faint)',
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            История
          </div>
          <EmptyState title="Пусто" hint="Журнал действий появится в Фазе 10." />
        </div>
      </div>

      {splitOpen && (
        <SplitDialog
          positions={proc.positions}
          onClose={() => setSplitOpen(false)}
          onSubmit={(payload) => splitMut.mutate(payload)}
          pending={splitMut.isPending}
        />
      )}
    </div>
  )
}

// ---- Header edit panel (sub-component) ------------------------------------

const headerFieldStyle = {
  display: 'flex',
  flexDirection: 'column' as const,
  gap: 3,
}

const headerInputStyle = {
  padding: '4px 8px',
  border: '1px solid var(--line)',
  borderRadius: 4,
  fontSize: 13,
  background: 'var(--surface)',
}

const headerLabelStyle = {
  fontSize: 10,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'var(--faint)',
  fontWeight: 600,
}

function HeaderEditPanel({
  draft,
  statusOptions,
  onChange,
  disabled,
}: {
  draft: HeaderDraft
  statusOptions: DictValue[] | null
  onChange: (key: keyof HeaderDraft, value: string) => void
  disabled: boolean
}) {
  return (
    <div style={{ marginTop: 10 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '8px 12px',
          maxWidth: 1000,
        }}
      >
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>№ заявки</label>
          <input
            style={headerInputStyle}
            value={draft.tender_num}
            onChange={(e) => onChange('tender_num', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>№ процедуры</label>
          <input
            style={headerInputStyle}
            value={draft.proc}
            onChange={(e) => onChange('proc', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>Поставщик</label>
          <input
            style={headerInputStyle}
            value={draft.supplier}
            placeholder="не выбран"
            onChange={(e) => onChange('supplier', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>Закупщик</label>
          <input
            style={headerInputStyle}
            value={draft.fio_zakupshchik}
            onChange={(e) => onChange('fio_zakupshchik', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>Нач. публ.</label>
          <input
            style={headerInputStyle}
            type="date"
            value={draft.pub_start}
            onChange={(e) => onChange('pub_start', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>Заверш. публ.</label>
          <input
            style={headerInputStyle}
            type="date"
            value={draft.pub_end}
            onChange={(e) => onChange('pub_end', e.target.value)}
            disabled={disabled}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>Статус закупки</label>
          <StatusSelect
            value={draft.status_zakup}
            options={(statusOptions ?? []).map((o) => o.value)}
            onSelect={(v) => onChange('status_zakup', v)}
            disabled={disabled}
          />
        </div>
      </div>
    </div>
  )
}

// ---- Split dialog (sub-component) -----------------------------------------

function SplitDialog({
  positions,
  onClose,
  onSubmit,
  pending,
}: {
  positions: ProcedurePosition[]
  onClose: () => void
  onSubmit: (payload: SplitPayload) => void
  pending: boolean
}) {
  // Local entries keyed off the server position ids; the dialog rebuilds on
  // each open (it's only rendered while open).
  const [entries, setEntries] = useState<SplitEntry[]>(() =>
    positions.map((p) => ({
      source_position_id: p.id,
      name: p.name,
      available: p.qty,
      qty: '',
    })),
  )
  const [supplier, setSupplier] = useState('')
  const [proc, setProc] = useState('')

  const setQty = (id: number, qty: string) =>
    setEntries((prev) =>
      prev.map((e) =>
        e.source_position_id === id
          ? { ...e, qty: qty.replace(/[^\d.,]/g, '').replace(',', '.') }
          : e,
      ),
    )

  const validated = entries
    .map((e) => ({
      ...e,
      n: Number(e.qty === '' ? 0 : e.qty),
    }))
    .filter((e) => e.n > 0 && e.n <= e.available)

  const valid = validated.length > 0

  function submit() {
    if (!valid || pending) return
    onSubmit({
      positions: validated.map((e) => ({
        source_position_id: e.source_position_id,
        qty: e.n,
      })),
      supplier: supplier.trim() || undefined,
      proc: proc.trim() || undefined,
    })
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Разбить по поставщикам"
      width={620}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={pending}>
            Отмена
          </button>
          <button
            className="btn primary"
            onClick={submit}
            disabled={!valid || pending}
          >
            {pending ? 'Разбиваем…' : 'Разбить'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10 }}>
        Укажите количество для каждой позиции, которое нужно перенести в новую
        процедуру-сестру. Исходная процедура будет уменьшена на это количество
        (MOVE-семантика).
      </div>
      <table
        className="postbl"
        style={{ tableLayout: 'fixed', width: '100%' }}
      >
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Позиция</th>
            <th style={{ width: 90, textAlign: 'right' }}>Доступно</th>
            <th style={{ width: 110, textAlign: 'right' }}>Разбить</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const n = Number(e.qty === '' ? 0 : e.qty)
            const over = e.qty !== '' && n > e.available
            return (
              <tr key={e.source_position_id}>
                <td>{e.name}</td>
                <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>
                  {e.available}
                </td>
                <td style={{ padding: '4px 6px' }}>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={e.qty}
                    onChange={(ev) => setQty(e.source_position_id, ev.target.value)}
                    placeholder="0"
                    style={{
                      width: '100%',
                      padding: '4px 6px',
                      border: `1px solid ${over ? 'var(--late)' : 'var(--line)'}`,
                      borderRadius: 3,
                      textAlign: 'right',
                      fontFamily: 'var(--mono)',
                      fontSize: 12,
                    }}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div
        style={{
          marginTop: 12,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
        }}
      >
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>Поставщик (новая, необязательно)</label>
          <input
            style={headerInputStyle}
            value={supplier}
            placeholder="не выбран"
            onChange={(e) => setSupplier(e.target.value)}
          />
        </div>
        <div style={headerFieldStyle}>
          <label style={headerLabelStyle}>№ процедуры (необязательно)</label>
          <input
            style={headerInputStyle}
            value={proc}
            onChange={(e) => setProc(e.target.value)}
          />
        </div>
      </div>
      {!valid && (
        <div
          style={{
            marginTop: 10,
            fontSize: 12,
            color: 'var(--late)',
          }}
        >
          Укажите хотя бы одну позицию с количеством &gt; 0 (не больше
          доступного).
        </div>
      )}
    </Modal>
  )
}
