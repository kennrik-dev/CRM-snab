/**
 * Pure view helpers for the «Оплаты» page (mirror of lib/supportView.ts).
 *
 * buildPayBar: turns the 4 summary.bar amounts into renderable segments in
 * canon order (paid → await → delivered-no-upd → contracted-no-delivery).
 * `widthPct` is the EXACT fractional percent (so the `.pbar` always sums to
 * 100% width); `labelPct` is the rounded percent shown inside the segment.
 * total = 0 → all segments 0 (the bar renders empty, no divide-by-zero).
 */
export type PayBarSegment = {
  cls: string
  value: number
  widthPct: number
  labelPct: number
}

export type PayBar = {
  paid: number
  await_: number
  delivered_no_upd: number
  contracted_no_delivery: number
}

export function buildPayBar(bar: PayBar): PayBarSegment[] {
  const total = bar.paid + bar.await_ + bar.delivered_no_upd + bar.contracted_no_delivery
  const seg = (cls: string, value: number): PayBarSegment => {
    const widthPct = total > 0 ? (value / total) * 100 : 0
    return { cls, value, widthPct, labelPct: Math.round(widthPct) }
  }
  return [
    seg('sp-paid', bar.paid),
    seg('sp-out', bar.await_),
    seg('sp-del', bar.delivered_no_upd),
    seg('sp-con', bar.contracted_no_delivery),
  ]
}
