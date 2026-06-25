/** Переключатель документа в поставке: `.doctag` (✓ зелёный, on) / `.no` (✕ красный, off). */
export function DocToggle({
  label,
  on,
  disabled,
  onClick,
}: {
  label: string
  on: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`doctag${on ? '' : ' no'}`}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      disabled={disabled}
      style={{ border: 'none', cursor: disabled ? 'default' : 'pointer', fontFamily: 'inherit' }}
    >
      {label}
    </button>
  )
}
