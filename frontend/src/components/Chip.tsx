export type ChipKind = 'wait' | 'proc' | 'supp' | 'pay' | 'ok' | 'late' | 'cancel'

export function Chip({
  kind,
  label,
  mini,
}: {
  kind: ChipKind
  label: string
  mini?: boolean
}) {
  const cls = `chip ${kind}${mini ? ' mini' : ''}`
  return (
    <span className={cls}>
      <i />
      {label}
    </span>
  )
}
