/** Статус оплаты УПД: `.pchip` + `.await` (Ожидает) / `.paid` (Оплачено) / `.late` (иное). */
const MAP: Record<string, { cls: string; label: string }> = {
  await: { cls: 'await', label: 'Ожидает оплаты' },
  paid: { cls: 'paid', label: 'Оплачено' },
}
export function PayChip({ payStatus }: { payStatus: string | null | undefined }) {
  if (!payStatus) return null
  const m = MAP[payStatus] ?? { cls: 'late', label: payStatus }
  return <span className={`pchip ${m.cls}`}>{m.label}</span>
}
