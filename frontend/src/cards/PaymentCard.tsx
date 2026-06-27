import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getPayment,
  patchPayment,
  payPayment,
  type PaymentDetail,
  type PaymentPatch,
} from '../api/payments'
import { Chip } from '../components/Chip'
import { EmptyState } from '../components/EmptyState'
import { payStatusChip } from '../lib/statusColors'
import { money, dateRu } from '../lib/format'
import { kopecksToRublesInput, rublesToKopecks } from '../lib/money'
import { canEdit } from '../lib/permissions'
import { useAuth } from '../auth/AuthContext'

type PayDraft = {
  supplier: string
  contract: string
  zrds: string
  srok: string
  amount: string // rubles input string
}

function draftFromPayment(p: PaymentDetail): PayDraft {
  return {
    supplier: p.supplier ?? '',
    contract: p.contract ?? '',
    zrds: p.zrds ?? '',
    srok: p.srok ?? '',
    amount: kopecksToRublesInput(p.amount),
  }
}

/** Diff draft vs server → only changed PaymentPatch fields (empty string → null). */
function buildPatch(d: PayDraft, p: PaymentDetail): PaymentPatch | null {
  const patch: PaymentPatch = {}
  const cur = draftFromPayment(p)
  const setStr = (field: keyof PaymentPatch, dk: keyof PayDraft) => {
    if (d[dk] !== cur[dk]) {
      ;(patch as Record<string, unknown>)[field as string] = d[dk] === '' ? null : d[dk]
    }
  }
  setStr('supplier', 'supplier')
  setStr('contract', 'contract')
  setStr('zrds', 'zrds')
  setStr('srok', 'srok')
  // money round-trip (как contract_sum в SupportCard)
  if (rublesToKopecks(d.amount) !== p.amount) {
    patch.amount = rublesToKopecks(d.amount)
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

export function PaymentCard() {
  const { id } = useParams()
  const paymentId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { permissions } = useAuth()
  const canEditThis = canEdit(permissions, 'soprovozhdenie')

  const payQ = useQuery({
    queryKey: ['payment', paymentId],
    queryFn: () => getPayment(paymentId),
    enabled: Number.isFinite(paymentId),
  })
  const p = payQ.data

  const [draft, setDraft] = useState<PayDraft | null>(null)
  const [savedTick, setSavedTick] = useState(0)
  const [actionErr, setActionErr] = useState<string | null>(null)

  // reset draft on payment change / load
  useEffect(() => {
    setDraft(null)
    setActionErr(null)
  }, [paymentId])

  const refresh = useCallback(async () => {
    // Await the card refetch BEFORE resetting the local draft (await-refetch-
    // before-reset pitfall — see SupportCard.refresh). Then invalidate the
    // list/summary/counter so the registry + hero reflect the change.
    await qc.refetchQueries({ queryKey: ['payment', paymentId] })
    qc.invalidateQueries({ queryKey: ['payments'] })
    setDraft(null)
  }, [qc, paymentId])

  const saveMut = useMutation({
    mutationFn: (payload: PaymentPatch) => patchPayment(paymentId, payload),
    onSuccess: async () => {
      await refresh()
      setSavedTick((t) => t + 1)
    },
    onError: (err) => setActionErr(lastErrorMessage(err)),
  })

  const payMut = useMutation({
    mutationFn: () => payPayment(paymentId),
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

  if (payQ.isLoading) return <div className="wrap"><p className="desc">Загрузка…</p></div>
  if (payQ.isError || !p)
    return (
      <div className="wrap">
        <EmptyState title="Платёж не найден" hint="Возможно, он удалён или нет прав." />
      </div>
    )

  const d = draft ?? draftFromPayment(p)
  const patch = draft ? buildPatch(draft, p) : null
  const status = payStatusChip(p.pay_status, p.is_overdue)
  const isPaid = p.pay_status === 'paid'
  const requestDisplay = p.request_label ?? p.delivery?.parent_code ?? null

  function setField<K extends keyof PayDraft>(k: K, v: PayDraft[K]) {
    setDraft((prev) => ({ ...(prev ?? draftFromPayment(p!)), [k]: v }))
  }

  // meta cells: editable ones render an <input>, the rest a read-only .v
  const editableCell = (label: string, key: keyof PayDraft, value: string, type?: string) => (
    <div className="m">
      <div className="l">{label}</div>
      {canEditThis ? (
        <input
          style={fieldStyle}
          type={type}
          inputMode={key === 'amount' ? 'decimal' : undefined}
          value={value}
          onChange={(e) => setField(key, e.target.value)}
        />
      ) : (
        <div className="v">{value || '—'}</div>
      )}
    </div>
  )
  const readOnlyCell = (label: string, value: string) => (
    <div className="m">
      <div className="l">{label}</div>
      <div className="v">{value || '—'}</div>
    </div>
  )

  return (
    <div className="wrap">
      <button className="back" onClick={() => navigate('/oplaty')}>
        ‹ Оплаты
      </button>

      <div className="pcd">
        <div className="pcd-h">
          <div className="top">
            <div style={{ flex: 1, minWidth: 260 }}>
              <h1>{p.upd}</h1>
              <div className="mt">
                <b>Заявка:</b> {requestDisplay ?? '—'} · <b>Поставка:</b>{' '}
                {p.delivery ? `№${p.delivery.n}` : '— (ручная УПД)'}
              </div>
            </div>
            <span className="sp" />
            <span className="amt-big">{money(p.amount)}</span>
          </div>
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
            <Chip kind={status.kind} label={status.label} />
            {p.pay_date && (
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                оплачено {dateRu(p.pay_date)}
              </span>
            )}
          </div>
          {actionErr && (
            <div style={{ color: 'var(--late)', fontSize: 12, marginTop: 8 }}>{actionErr}</div>
          )}
        </div>

        <div className="pcd-meta">
          {readOnlyCell('Заявка', requestDisplay ?? '')}
          {editableCell('Поставщик', 'supplier', d.supplier)}
          {editableCell('Договор', 'contract', d.contract)}
          {editableCell('№ ЗРДС', 'zrds', d.zrds)}
          {editableCell('Срок', 'srok', d.srok, 'date')}
          {editableCell('Сумма с НДС (₽)', 'amount', d.amount)}
          {readOnlyCell('Дата оплаты', p.pay_date ? dateRu(p.pay_date) : '')}
          {readOnlyCell(
            'Поставка',
            p.delivery ? `№${p.delivery.n} · ${p.delivery.parent_code ?? '—'}` : '',
          )}
        </div>

        <div className="pcd-body">
          <div
            className="actbar"
            style={{ background: 'transparent', border: 'none', padding: '0 0 14px' }}
          >
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
            <span className="sp" />
            {canEditThis && (
              <button
                className="btn primary"
                disabled={isPaid || payMut.isPending}
                onClick={() => {
                  if (isPaid || payMut.isPending) return
                  if (window.confirm('Провести оплату? Дата оплаты будет зафиксирована.')) {
                    payMut.mutate()
                  }
                }}
              >
                {payMut.isPending ? 'Оплата…' : 'Провести оплату'}
              </button>
            )}
          </div>

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
            Позиции в УПД ({p.positions.length})
          </div>
          <div className="tbl-scroll">
            <table className="postbl">
              <thead>
                <tr>
                  <th>№</th>
                  <th>Наименование</th>
                  <th>Ед.</th>
                  <th>Кол-во</th>
                  <th>Цена с НДС</th>
                  <th>Сумма</th>
                </tr>
              </thead>
              <tbody>
                {p.positions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      Нет позиций
                    </td>
                  </tr>
                ) : (
                  p.positions.map((pos) => (
                    <tr key={pos.id}>
                      <td>{pos.n ?? '—'}</td>
                      <td>{pos.name ?? '—'}</td>
                      <td>{pos.unit ?? '—'}</td>
                      <td>{pos.qty ?? '—'}</td>
                      <td>{money(pos.price)}</td>
                      <td>
                        {money(
                          pos.price != null && pos.qty != null
                            ? Math.round(pos.qty * pos.price)
                            : null,
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
