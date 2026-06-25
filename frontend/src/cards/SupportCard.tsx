import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getProcedure, patchProcedure, type ProcedureDetail, type ProcedurePatch } from '../api/procedures'
import { getRequest } from '../api/requests'
import { listDict } from '../api/dict'
import { STATUS_POSTAVKI } from '../api/support'
import { StatusSelect } from '../components/StatusSelect'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import { sdelkiStatusChip, postavkiStatusChip } from '../lib/statusColors'
import { money } from '../lib/format'
import { kopecksToRublesInput, rublesToKopecks } from '../lib/money'
import { sumPositionsKopecks, sisterRoute } from '../lib/supportView'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'
import { DeliverySection } from '../components/support/DeliverySection'

type SoppDraft = {
  contract: string
  fio_dogovornik: string
  contract_sum: string // rubles input string
  status_sdelki: string
  status_postavki: string
  srok_dd: string
  plan_date: string
  fakt_date: string
}

function draftFromProc(p: ProcedureDetail): SoppDraft {
  return {
    contract: p.contract ?? '',
    fio_dogovornik: p.fio_dogovornik ?? '',
    contract_sum: kopecksToRublesInput(p.contract_sum),
    status_sdelki: p.status_sdelki ?? '',
    status_postavki: p.status_postavki ?? '',
    srok_dd: p.srok_dd ?? '',
    plan_date: p.plan_date ?? '',
    fakt_date: p.fakt_date ?? '',
  }
}

/** Diff драфта vs процедуры → только изменённые Б2-поля (empty string → null). */
function buildSoppPatch(d: SoppDraft, p: ProcedureDetail): ProcedurePatch | null {
  const patch: ProcedurePatch = {}
  const cur = draftFromProc(p)
  const setStr = (field: keyof ProcedurePatch, dk: keyof SoppDraft) => {
    if (d[dk] !== cur[dk]) (patch as Record<string, unknown>)[field as string] = d[dk] === '' ? null : d[dk]
  }
  setStr('contract', 'contract')
  setStr('fio_dogovornik', 'fio_dogovornik')
  setStr('status_sdelki', 'status_sdelki')
  setStr('status_postavki', 'status_postavki')
  setStr('srok_dd', 'srok_dd')
  setStr('plan_date', 'plan_date')
  setStr('fakt_date', 'fakt_date')
  // money round-trip (как price в ProcedureCard):
  if (rublesToKopecks(d.contract_sum) !== p.contract_sum) {
    patch.contract_sum = rublesToKopecks(d.contract_sum)
  }
  return Object.keys(patch).length ? patch : null
}

function lastErrorMessage(err: unknown): string {
  const e = err as { body?: { detail?: string } } | null
  return e?.body?.detail ?? 'Не удалось сохранить'
}

const fieldStyle: CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: 6,
  padding: '6px 8px',
  fontFamily: 'inherit',
  fontSize: 13,
  width: '100%',
}
const labelStyle: CSSProperties = { fontSize: 11, color: 'var(--muted)', marginBottom: 3, display: 'block' }

export function SupportCard() {
  const { id } = useParams()
  const procedureId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')

  const procQ = useQuery({
    queryKey: ['procedure', procedureId],
    queryFn: () => getProcedure(procedureId),
    enabled: Number.isFinite(procedureId),
  })
  const proc = procQ.data

  const parentQ = useQuery({
    queryKey: ['request', proc?.parent_id],
    queryFn: () => getRequest(proc!.parent_id),
    enabled: !!proc,
  })

  const sdelkiDict = useQuery({
    queryKey: ['dict', 'status_sdelki'],
    queryFn: () => listDict('status_sdelki'),
  })
  const sdelkiOptions = sdelkiDict.data?.map((d) => d.value) ?? []

  const [draft, setDraft] = useState<SoppDraft | null>(null)
  const [savedTick, setSavedTick] = useState(0)
  const [actionErr, setActionErr] = useState<string | null>(null)

  // reset draft on procedure change (sister-switcher) / load
  useEffect(() => {
    setDraft(null)
    setActionErr(null)
  }, [procedureId])

  const refresh = useCallback(async () => {
    // Await the card refetch BEFORE resetting the local draft. The draft is
    // re-seeded during render from procQ.data; if we only invalidate, the
    // re-seed reads a PRE-save snapshot and the next save reverts the change
    // (await-refetch-before-reset pitfall, see ProcedureCard.refresh).
    await qc.refetchQueries({ queryKey: ['procedure', procedureId] })
    qc.invalidateQueries({ queryKey: ['support'] })
    if (proc?.parent_id) qc.invalidateQueries({ queryKey: ['request', proc.parent_id] })
    setDraft(null)
  }, [qc, procedureId, proc?.parent_id])

  const saveMut = useMutation({
    mutationFn: (payload: ProcedurePatch) => patchProcedure(procedureId, payload),
    onSuccess: async () => {
      await refresh()
      setSavedTick((t) => t + 1)
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  useEffect(() => {
    if (!savedTick) return
    const idt = setTimeout(() => setSavedTick(0), 2500)
    return () => clearTimeout(idt)
  }, [savedTick])

  if (procQ.isLoading) return <div className="wrap"><p className="desc">Загрузка…</p></div>
  if (procQ.isError || !proc)
    return (
      <div className="wrap">
        <EmptyState title="Процедура не найдена" hint="Возможно, она удалена или нет прав." />
      </div>
    )

  const d = draft ?? draftFromProc(proc)
  const patch = draft ? buildSoppPatch(draft, proc) : null
  const sisters =
    parentQ.data?.tenders.find((t) => t.id === proc.tender_id)?.procedures ?? []
  const positionsSum = sumPositionsKopecks(proc.positions)
  const awaiting = proc.positions.filter((p) => p.delivery_id == null)

  function setField<K extends keyof SoppDraft>(k: K, v: SoppDraft[K]) {
    setDraft((prev) => ({ ...(prev ?? draftFromProc(proc!)), [k]: v }))
  }

  return (
    <div className="wrap">
      <button className="back" onClick={() => navigate('/soprovozhdenie')}>
        ‹ В сопровождении
      </button>

      {/* Sister switcher — единого вида с карточкой закупки (.crumbs + .sib) */}
      {sisters.length > 1 && (
        <div className="crumbs" style={{ marginBottom: 10 }}>
          <span className="pcode">{proc.code}</span>
          {sisters.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`sib${s.id === proc.id ? ' on' : ''}`}
              onClick={() => navigate(sisterRoute(s.block, s.id))}
            >
              {s.proc ?? `#${s.id}`}
            </button>
          ))}
          <span className="sp" />
        </div>
      )}

      <div className="page-h">
        <h1>
          <span className="tnum" style={{ color: 'var(--supp)' }}>{proc.code}</span> {proc.title}
        </h1>
        <span className="sp" />
      </div>

      <div className="block reg" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
        <div className="block-h">
          <span className="bnum">Б2</span>
          <span className="btitle">Сопровождение</span>
          <span className="sp" style={{ flex: 1 }} />
          {canEditThis && (
            <button
              className="btn primary"
              disabled={!patch || saveMut.isPending}
              onClick={() => patch && saveMut.mutate(patch)}
            >
              {saveMut.isPending ? 'Сохранение…' : 'Сохранить'}
            </button>
          )}
          {savedTick > 0 && <span style={{ color: 'var(--ok)', fontSize: 12 }}>✓ Сохранено</span>}
          {actionErr && <span style={{ color: 'var(--late)', fontSize: 12 }}>{actionErr}</span>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, padding: 12 }}>
          <div>
            <span style={labelStyle}>№ заявки</span>
            <div style={fieldStyle}>{proc.tender_num ?? '—'}</div>
          </div>
          <div>
            <span style={labelStyle}>№ процедуры</span>
            <div style={fieldStyle}>{proc.proc ?? '—'}</div>
          </div>
          <div>
            <span style={labelStyle}>Поставщик</span>
            <div style={fieldStyle}>{proc.supplier ?? '—'}</div>
          </div>

          <div>
            <span style={labelStyle}>Договор</span>
            <input
              style={fieldStyle}
              disabled={!canEditThis}
              value={d.contract}
              onChange={(e) => setField('contract', e.target.value)}
            />
          </div>
          <div>
            <span style={labelStyle}>ФИО договорника</span>
            <input
              style={fieldStyle}
              disabled={!canEditThis}
              value={d.fio_dogovornik}
              onChange={(e) => setField('fio_dogovornik', e.target.value)}
            />
          </div>
          <div>
            <span style={labelStyle}>Сумма договора (₽)</span>
            <input
              style={fieldStyle}
              disabled={!canEditThis}
              value={d.contract_sum}
              inputMode="decimal"
              onChange={(e) => setField('contract_sum', e.target.value)}
            />
            <span style={{ ...labelStyle, marginTop: 2 }}>Σ позиций: {money(positionsSum)}</span>
          </div>

          <div>
            <span style={labelStyle}>Статус сделки</span>
            {canEditThis ? (
              <StatusSelect
                value={d.status_sdelki}
                options={sdelkiOptions}
                onSelect={(v) => setField('status_sdelki', v)}
                color={sdelkiStatusChip}
              />
            ) : (
              <Chip {...sdelkiStatusChip(d.status_sdelki)} mini />
            )}
          </div>
          <div>
            <span style={labelStyle}>Статус поставки</span>
            {canEditThis ? (
              <StatusSelect
                value={d.status_postavki}
                options={[...STATUS_POSTAVKI]}
                onSelect={(v) => setField('status_postavki', v)}
                color={postavkiStatusChip}
              />
            ) : (
              <Chip {...postavkiStatusChip(d.status_postavki)} mini />
            )}
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <label style={{ flex: 1 }}>
              <span style={labelStyle}>Срок ДД</span>
              <input type="date" style={fieldStyle} disabled={!canEditThis} value={d.srok_dd} onChange={(e) => setField('srok_dd', e.target.value)} />
            </label>
            <label style={{ flex: 1 }}>
              <span style={labelStyle}>План</span>
              <input type="date" style={fieldStyle} disabled={!canEditThis} value={d.plan_date} onChange={(e) => setField('plan_date', e.target.value)} />
            </label>
            <label style={{ flex: 1 }}>
              <span style={labelStyle}>Факт</span>
              <input type="date" style={fieldStyle} disabled={!canEditThis} value={d.fakt_date} onChange={(e) => setField('fakt_date', e.target.value)} />
            </label>
          </div>
        </div>
      </div>

      {/* Позиции — read-only (в Б2 позиции не редактируются, только уходят в поставки) */}
      <div className="block reg" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
        <div className="block-h">
          <span className="btitle">Позиции процедуры ({proc.positions.length})</span>
        </div>
        <div className="tbl-scroll">
          <table className="postbl">
            <thead>
              <tr>
                <th>Наименование</th>
                <th>Кол-во</th>
                <th>Ед.</th>
                <th>Цена с НДС</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {proc.positions.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.qty}</td>
                  <td>{p.unit ?? '—'}</td>
                  <td>{money(p.price)}</td>
                  <td>{money(p.price != null ? Math.round(p.qty * p.price) : null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ожидают отгрузки — read-only в 6.3.5a; интерактив (Создать поставку) подключается в 6.3.5b */}
      <div className="block reg" style={{ '--bc': 'var(--supp)' } as CSSProperties}>
        <div className="block-h">
          <span className="btitle">Ожидают отгрузки ({awaiting.length})</span>
        </div>
        <div style={{ padding: 12 }}>
          {awaiting.length === 0 ? (
            <EmptyState title="Все позиции в поставках" />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {awaiting.map((p) => (
                <li key={p.id}>{p.name} — {p.qty} {p.unit ?? ''}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <DeliverySection proc={proc} canEditThis={canEditThis} refresh={refresh} />
    </div>
  )
}
