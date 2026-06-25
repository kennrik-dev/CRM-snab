import type { ChipKind } from '../components/Chip'

// Each status_zakup value gets its OWN color (like Комплектация's colored
// chips), so the 6 справочник values + «Новая» + «Отменена» are visually
// distinct. RED (--late) is reserved for «Отменена» ONLY — no other status is
// red. The other 7 statuses use gray / orange / blue / purple / teal / rose /
// green (the stage palette has 6 hues, so «teal» and «rose» were added).
const STATUS_KIND: Record<string, ChipKind> = {
  'Приём заявок': 'proc',
  'Торги': 'supp',
  'Тех. экспертиза': 'pay',
  'Дозапросы': 'teal',
  'Согласование': 'rose',
  'На сделку': 'ok',
}

/**
 * status_zakup → { chip kind, label }. Pure; unit-tested.
 * - «Отменена» → late (red) — the ONLY red status.
 * - NULL / "" → wait (gray), labelled «В закупке».
 * - «Новая» (service-set on take-to-work) → wait (gray).
 * - a known справочник value → its own hue, label verbatim.
 * - anything else → proc (orange) fallback.
 */
export function procStatusChip(
  status_zakup: string | null | undefined,
): { kind: ChipKind; label: string } {
  if (status_zakup === 'Отменена') return { kind: 'late', label: 'Отменена' }
  if (!status_zakup || status_zakup === '') return { kind: 'wait', label: 'В закупке' }
  if (status_zakup === 'Новая') return { kind: 'wait', label: 'Новая' }
  return { kind: STATUS_KIND[status_zakup] ?? 'proc', label: status_zakup }
}

/**
 * status_sdelki → { chip kind, label }. Pure; unit-tested.
 * Значения — из dict kind 'status_sdelki' (3 значения). RED не используется.
 * - NULL / "" → wait (gray), «Не задано».
 * - Подписано → ok; Подготовка ДД → teal; Согласование → wait.
 * - иное → proc fallback.
 */
export function sdelkiStatusChip(
  v: string | null | undefined,
): { kind: ChipKind; label: string } {
  if (!v || v === '') return { kind: 'wait', label: 'Не задано' }
  switch (v) {
    case 'Подписано':
      return { kind: 'ok', label: v }
    case 'Подготовка ДД':
      return { kind: 'teal', label: v }
    case 'Согласование':
      return { kind: 'wait', label: v }
    default:
      return { kind: 'proc', label: v }
  }
}

/**
 * status_postavki → { chip kind, label }. Pure; unit-tested.
 * 6-значный enum. RED (late) — только «Отменена» (консистентно с status_zakup).
 * - NULL / "" → wait (gray), «Не задано».
 * - иное → proc fallback.
 */
export function postavkiStatusChip(
  v: string | null | undefined,
): { kind: ChipKind; label: string } {
  if (!v || v === '') return { kind: 'wait', label: 'Не задано' }
  switch (v) {
    case 'Отменена':
      return { kind: 'late', label: v }
    case 'Поставлено':
      return { kind: 'ok', label: v }
    case 'Частично поставлено':
      return { kind: 'pay', label: v }
    case 'В поставке':
      return { kind: 'supp', label: v }
    case 'В производстве':
      return { kind: 'teal', label: v }
    case 'Новая':
      return { kind: 'wait', label: v }
    default:
      return { kind: 'proc', label: v }
  }
}
