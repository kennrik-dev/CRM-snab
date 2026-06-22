import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import { PositionTable, type PositionTableColumn } from '../components/PositionTable'
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
  num?: string | null
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
    num: null,
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
    num: p.num,
    name: p.name,
    qty: p.qty,
    unit: p.unit,
    gost_tu: p.gost_tu,
    doc_code: p.doc_code,
  }
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

  async function refresh() {
    // Await the card refetch BEFORE resetting editRows. editRows is re-seeded
    // during render from query.data; if we only invalidate, query.data is
    // still the PRE-save snapshot at re-seed time, so editRows gets seeded
    // with stale values and the next save REVERTS the position (oscillation /
    // "values change on save"). Awaiting guarantees the re-seed reads fresh
    // data. (Same pattern as CreateRequestModal's onSuccess.)
    await qc.refetchQueries({ queryKey: ['request', requestId] })
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

  // PositionTable wiring — controlled by the parent editRows state. The
  // delete handler routes server rows through `removedIds` so they get
  // DELETEd on save, and drops local-only rows.
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

  const onDeleteRow = useCallback(
    (rowId: string | number) => {
      setEditRows((prev) => {
        const cur = prev ?? []
        const target = cur.find((r) => r._localId === rowId)
        const targetId = target?.id
        if (targetId !== undefined) {
          setRemovedIds((ids) => [...ids, targetId])
        }
        const next = cur.filter((r) => r._localId !== rowId)
        return next.length === 0 ? [makeLocalRow()] : next
      })
    },
    [],
  )

  const onAddRows = useCallback(
    (afterRowId: string | number | null, count: number): string[] => {
      // Build the new rows synchronously so we can return their ids. The
      // same array is then spliced into setRows' functional update — no
      // double-makeLocalRow, no race with the re-render.
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

  // PositionTable column definitions. Widths sum to ~1080 (the .dcard
  // max-width minus padding) so the table never horizontal-scrolls.
  const positionColumns = useMemo<PositionTableColumn<EditableRow>[]>(
    () => [
      { key: 'name', header: 'Наименование', width: 'minmax(180px, 1fr)' },
      { key: 'qty', header: 'Кол-во', width: '90px', align: 'right', mono: true },
      { key: 'unit', header: 'Ед. изм.', width: '80px', mono: true },
      { key: 'gost_tu', header: 'ГОСТ/ТУ', width: '140px' },
      { key: 'doc_code', header: 'Шифр документации', width: '180px' },
    ],
    [],
  )

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
        if ((row.num ?? null) !== (prev.num ?? null)) patch.num = row.num ?? null
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
          num: r.num ?? null,
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
          <PositionTable<EditableRow>
            rows={editRows ?? req.positions.map(toEditable)}
            columns={positionColumns}
            getRowId={(r) => r._localId}
            onCellChange={onCellChange}
            onDeleteRow={onDeleteRow}
            onAddRows={onAddRows}
            readOnly={!canEditKomp || !isAwaiting}
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
