import { useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import {
  PositionTable,
  type PositionTableColumn,
} from '../components/PositionTable'
import { getProcedure, type ProcedurePosition } from '../api/procedures'
import { getRequest, type ProcedureOut } from '../api/requests'
import { procStatusChip } from '../pages/Zakupka'
import { dateRu, money } from '../lib/format'

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

// ---- Procedure-position row (read-only) -----------------------------------

type ProcRow = ProcedurePosition

// ---- Component ------------------------------------------------------------

export function ProcedureCard() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const procedureId = id ? Number(id) : NaN

  const query = useQuery({
    queryKey: ['procedure', procedureId],
    queryFn: () => getProcedure(procedureId),
    enabled: Number.isFinite(procedureId),
  })

  const proc = query.data

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

  const total = proc ? sumPositionsKopecks(proc.positions) : 0

  // Read-only column definitions. The price column uses `format` to render
  // kopecks as money; the editing <input> would use the raw value (but the
  // table is readOnly in this round).
  const columns = useMemo<PositionTableColumn<ProcRow>[]>(
    () => [
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
        format: (v) => (v ? money(Number(v)) : '—'),
      },
    ],
    [],
  )

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

  return (
    <div className="wrap">
      <button className="back" onClick={() => navigate('/zakupka')}>
        ‹ Назад
      </button>

      <div className="dcard">
        <div className="dhead">
          <div className="crumbs">
            <span className="pcode">{proc.code}</span>
            {/* Sister-switcher: one chip per procedure of the same tender.
                Current is highlighted (.on). Read-only round — clicking only
                navigates between sisters. */}
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
            </div>
          </div>
        </div>

        {/* Read-only round: minimal action bar — just the position count.
            Split / to-support / cancel / edit arrive in round B2. */}
        <div className="actbar">
          <span className="z">
            Позиций: <b>{proc.positions.length}</b>
          </span>
          <span className="sp" />
          <span className="z" style={{ color: 'var(--late)' }}>
            Редактирование — в следующем раунде
          </span>
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
            Позиции процедуры
          </div>
          <PositionTable<ProcRow>
            rows={proc.positions}
            columns={columns}
            getRowId={(r) => r.id}
            // Read-only round: the table never calls these handlers (readOnly
            // disables all editing/deletion), but the Props type requires them.
            onCellChange={() => {}}
            onDeleteRow={() => {}}
            readOnly
            showRowNumber={false}
            emptyMessage="Нет позиций"
          />
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
    </div>
  )
}
