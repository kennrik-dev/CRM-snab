import { useCallback, useMemo, useState, type CSSProperties } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ColumnDef } from '../components/types'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import { ExcelTable } from '../components/ExcelTable'
import { useAuth } from '../auth/AuthContext'
import {
  addPositions,
  cancelRequest,
  deletePosition,
  duplicateRequest,
  getRequest,
  patchPosition,
  takeToWork,
  uncancelRequest,
  type RequestPosition,
  type RequestPositionInput,
} from '../api/requests'
import { canEdit } from '../lib/permissions'
import { dateRu } from '../lib/format'

// ---- Editable position row ------------------------------------------------

type EditableRow = {
  _localId: string
  id?: number
  name: string | null
  qty: number | null
  unit: string | null
  gost_tu: string | null
  doc_code: string | null
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
  }
}

function toEditable(p: RequestPosition): EditableRow {
  return {
    _localId: `pos-${p.id}`,
    id: p.id,
    name: p.name,
    qty: p.qty,
    unit: p.unit,
    gost_tu: p.gost_tu,
    doc_code: p.doc_code,
  }
}

const POSITION_COLUMNS_BASE: Omit<ColumnDef<EditableRow>, 'render'>[] = [
  { key: 'name', header: 'Наименование', type: 'text', width: 'minmax(180px, 3fr)' },
  { key: 'qty', header: 'Кол-во', type: 'number', width: 'minmax(80px, 1fr)', align: 'right' },
  { key: 'unit', header: 'Ед. изм.', type: 'text', width: 'minmax(70px, 1fr)' },
  { key: 'gost_tu', header: 'ГОСТ/ТУ', type: 'text', width: 'minmax(90px, 1fr)' },
  { key: 'doc_code', header: 'Шифр документации', type: 'text', width: 'minmax(110px, 1fr)' },
]

const deleteBtnStyle: CSSProperties = {
  background: 'transparent',
  border: 0,
  color: 'var(--late)',
  cursor: 'pointer',
  fontSize: 16,
  padding: '0 4px',
  lineHeight: 1,
  borderRadius: 3,
}

// ---- Helpers --------------------------------------------------------------

function lastErrorMessage(err: unknown): string {
  const apiErr = err as { body?: { detail?: string } }
  return apiErr?.body?.detail ?? 'Не удалось выполнить действие'
}

// ---- Component ------------------------------------------------------------

export function RequestCard() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const requestId = id ? Number(id) : NaN
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditKomp = canEdit(permissions, 'komplektaciya')
  const canEditZak = canEdit(permissions, 'zakupka')

  const query = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => getRequest(requestId),
    enabled: Number.isFinite(requestId),
  })

  const req = query.data

  const [removedIds, setRemovedIds] = useState<number[]>([])
  const [editRows, setEditRows] = useState<EditableRow[] | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  // When server data first arrives, seed local edit rows (only if user can
  // edit and status is awaiting). We check `editRows === null` so we don't
  // stomp on subsequent user edits.
  if (req && editRows === null && canEditKomp && req.status === 'awaiting') {
    setEditRows(req.positions.map(toEditable))
  }

  function refresh() {
    qc.invalidateQueries({ queryKey: ['request', requestId] })
    qc.invalidateQueries({ queryKey: ['requests'] })
    setRemovedIds([])
    setEditRows(null)
  }

  // ---- Mutations ----------------------------------------------------------

  const cancelMut = useMutation({
    mutationFn: () => cancelRequest(requestId),
    onSuccess: () => refresh(),
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const uncancelMut = useMutation({
    mutationFn: () => uncancelRequest(requestId),
    onSuccess: () => refresh(),
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const duplicateMut = useMutation({
    mutationFn: () => {
      const newCode = window.prompt('Код для копии:', `${req?.code ?? ''}-копия`)
      if (!newCode) throw new Error('cancelled')
      return duplicateRequest(requestId, newCode)
    },
    onSuccess: (newReq) => {
      refresh()
      navigate(`/komplektaciya/${newReq.id}`)
    },
    onError: (err) => {
      if ((err as Error).message === 'cancelled') return
      setActionErr(lastErrorMessage(err))
    },
  })

  const takeToWorkMut = useMutation({
    mutationFn: () => takeToWork(requestId),
    onSuccess: () => {
      refresh()
      navigate('/komplektaciya')
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  // ---- Position editing --------------------------------------------------

  function onRowsChange(next: EditableRow[]) {
    // Detect deletions vs server rows (had id, no longer present)
    const beforeIds = new Set(
      (editRows ?? []).map((r) => r.id).filter((x): x is number => x !== undefined),
    )
    const afterIds = new Set(
      next.map((r) => r.id).filter((x): x is number => x !== undefined),
    )
    const newlyRemoved: number[] = []
    beforeIds.forEach((id) => {
      if (!afterIds.has(id)) newlyRemoved.push(id)
    })
    if (newlyRemoved.length > 0) {
      setRemovedIds((prev) => [...prev, ...newlyRemoved])
    }
    setEditRows(next.length === 0 ? [makeLocalRow()] : next)
  }

  // Per-row delete handler (from the trailing "×" column). Server rows are
  // marked for deletion via `removedIds` and sent on save; local-only rows
  // (no server id) are simply dropped from the edit array.
  const onDeleteRow = useCallback((localId: string) => {
    const cur = editRows ?? []
    const target = cur.find((r) => r._localId === localId)
    const targetId = target?.id
    if (targetId !== undefined) {
      setRemovedIds((ids) => [...ids, targetId])
    }
    const next = cur.filter((r) => r._localId !== localId)
    setEditRows(next.length === 0 ? [makeLocalRow()] : next)
  }, [editRows])

  // ExcelTable columns — "№" + 5 fields + per-row delete. When the card is
  // read-only (not awaiting, or user lacks edit rights) the column
  // definitions are returned without the delete button.
  // NOTE: declared before the render-section `isAwaiting` local below.
  const positionColumns = useMemo<ColumnDef<EditableRow>[]>(() => {
    const editable = canEditKomp && req?.status === 'awaiting'
    const base: ColumnDef<EditableRow>[] = [
      {
        key: '_idx',
        header: '№',
        width: '40px',
        editable: false,
        align: 'center',
        render: ({ rowIndex }) => <span className="num">{rowIndex + 1}</span>,
      },
      ...POSITION_COLUMNS_BASE.map(
        (c) => ({ ...c, editable: true }) as ColumnDef<EditableRow>,
      ),
    ]
    if (!editable) return base
    return [
      ...base,
      {
        key: '_del',
        header: '',
        width: '36px',
        editable: false,
        render: ({ row }) => (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onDeleteRow(row._localId)
            }}
            title="Удалить позицию"
            aria-label="Удалить позицию"
            style={deleteBtnStyle}
          >
            ×
          </button>
        ),
      },
    ]
  }, [canEditKomp, req?.status, onDeleteRow])

  async function savePositions() {
    if (!editRows) return
    setActionErr(null)
    try {
      const original = req?.positions ?? []
      // 1. Patch each existing row that changed.
      for (const row of editRows) {
        if (row.id === undefined) continue
        const prev = original.find((p) => p.id === row.id)
        if (!prev) continue
        const patch: Partial<RequestPosition> = {}
        if ((row.name ?? '') !== prev.name) patch.name = row.name ?? ''
        if (Number(row.qty ?? 0) !== Number(prev.qty)) patch.qty = Number(row.qty ?? 0)
        if ((row.unit ?? null) !== (prev.unit ?? null)) patch.unit = row.unit ?? null
        if ((row.gost_tu ?? null) !== (prev.gost_tu ?? null)) patch.gost_tu = row.gost_tu ?? null
        if ((row.doc_code ?? null) !== (prev.doc_code ?? null)) patch.doc_code = row.doc_code ?? null
        if (Object.keys(patch).length > 0) {
          await patchPosition(requestId, row.id, patch)
        }
      }
      // 2. Mass-insert new (id-less) rows that have name+qty.
      const newRows: RequestPositionInput[] = editRows
        .filter(
          (r) =>
            r.id === undefined &&
            (r.name ?? '').trim() !== '' &&
            r.qty != null,
        )
        .map((r) => ({
          name: (r.name ?? '').trim(),
          qty: Number(r.qty),
          unit: r.unit ?? null,
          gost_tu: r.gost_tu ?? null,
          doc_code: r.doc_code ?? null,
        }))
      if (newRows.length > 0) {
        await addPositions(requestId, newRows)
      }
      // 3. Delete rows the user removed.
      for (const id of removedIds) {
        await deletePosition(requestId, id)
      }
      refresh()
    } catch (err) {
      setActionErr(lastErrorMessage(err))
    }
  }

  // ---- Render -------------------------------------------------------------

  if (!Number.isFinite(requestId)) {
    return (
      <div className="wrap">
        <button className="back" onClick={() => navigate('/komplektaciya')}>
          ‹ Назад
        </button>
        <EmptyState title="Некорректный идентификатор заявки" />
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <div className="wrap">
        <button className="back" onClick={() => navigate('/komplektaciya')}>
          ‹ Назад
        </button>
        <div className="empty-state">Загрузка…</div>
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="wrap">
        <button className="back" onClick={() => navigate('/komplektaciya')}>
          ‹ Назад
        </button>
        <EmptyState title="Ошибка загрузки" hint={lastErrorMessage(query.error)} />
      </div>
    )
  }

  if (!req) return null

  const isAwaiting = req.status === 'awaiting'

  return (
    <div className="wrap">
      <button className="back" onClick={() => navigate('/komplektaciya')}>
        ‹ Назад
      </button>

      <div className="dcard">
        <div className="dhead">
          <div className="crumbs">
            <span className="pcode">{req.code}</span>
            {req.dept && <span className="sib">{req.dept}</span>}
            <span className="sp" />
            <Chip
              kind={isAwaiting ? 'wait' : 'cancel'}
              label={isAwaiting ? 'Ожидают закупки' : 'Отменена'}
              mini
            />
          </div>
          <div className="top">
            <div style={{ flex: 1, minWidth: 280 }}>
              <h1>
                {req.code}
                <small>{req.title}</small>
              </h1>
              <div className="mt">
                <b>Тип МТР:</b> {req.mtr ?? '—'} · <b>Срок:</b> {dateRu(req.srok)} ·
                {' '}<b>Дата загрузки:</b> {dateRu(req.zagruzka)} ·{' '}
                <b>Составитель:</b> {req.sostavitel}
              </div>
            </div>
          </div>
        </div>

        <div className="actbar">
          <span className="z">
            Позиций: <b>{req.positions.length}</b>
          </span>
          <span className="sp" />
          {canEditKomp && (
            <>
              {isAwaiting ? (
                <button
                  className="btn"
                  onClick={() => cancelMut.mutate()}
                  disabled={cancelMut.isPending}
                >
                  Отменить
                </button>
              ) : (
                <button
                  className="btn"
                  onClick={() => uncancelMut.mutate()}
                  disabled={uncancelMut.isPending}
                >
                  Вернуть из отмены
                </button>
              )}
              <button
                className="btn"
                onClick={() => duplicateMut.mutate()}
                disabled={duplicateMut.isPending}
              >
                Дублировать
              </button>
              <button
                className="btn primary"
                onClick={savePositions}
                disabled={!isAwaiting}
              >
                Сохранить изменения
              </button>
            </>
          )}
          {canEditZak && isAwaiting && (
            <button
              className="btn primary"
              onClick={() => takeToWorkMut.mutate()}
              disabled={takeToWorkMut.isPending}
            >
              {takeToWorkMut.isPending ? 'Принятие…' : 'Взять в работу'}
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
            Позиции
          </div>
          <ExcelTable<EditableRow>
            rows={editRows ?? req.positions.map(toEditable)}
            columns={positionColumns}
            getRowId={(r) => r._localId}
            readOnly={!canEditKomp || !isAwaiting}
            onRowsChange={onRowsChange}
            emptyMessage="Нет позиций"
          />
        </div>

        <div style={{ padding: '14px 22px 22px' }}>
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
      </div>
    </div>
  )
}
