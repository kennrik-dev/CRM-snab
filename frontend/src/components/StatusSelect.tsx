import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { procStatusChip } from '../lib/statusColors'

/**
 * StatusSelect — a colored status CHIP that opens a popover of colored chips,
 * each option in its OWN color (matching the Комплектация chip design). Replaces
 * a native <select>, which (a) can't render per-option colors and (b) doesn't
 * look like a chip.
 *
 * The closed control is a `.chip {kind} mini` button (current status color +
 * dot + ▾). The popover is rendered via a portal to <body> with position:fixed
 * so it is never clipped by the table's scroll container (.tbl-scroll has
 * overflow-x:auto, which per CSS spec also clips the y-axis). Closes on outside
 * click, Escape, and any scroll/resize (so the popover never detaches from the
 * chip). All interactions stopPropagation so a containing row's onRowClick
 * (navigation) does not fire.
 */
const POP_W = 184

export function StatusSelect({
  value,
  options,
  onSelect,
  disabled = false,
}: {
  value: string | null | undefined
  options: string[]
  onSelect: (status: string) => void
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const btnRef = useRef<HTMLButtonElement | null>(null)
  const popRef = useRef<HTMLDivElement | null>(null)

  function openMenu() {
    if (disabled) return
    const r = btnRef.current?.getBoundingClientRect()
    if (r) {
      // Below the chip, right-aligned to its right edge (status is the last
      // column, so the popover opens leftward into the table). Clamp to viewport.
      const left = Math.max(8, Math.min(r.right - POP_W, window.innerWidth - POP_W - 8))
      setCoords({ top: r.bottom + 3, left })
    }
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (popRef.current?.contains(t) || btnRef.current?.contains(t)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const close = () => setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [open])

  const cur = procStatusChip(value)

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={`chip ${cur.kind} mini`}
        onClick={(e) => {
          e.stopPropagation()
          openMenu()
        }}
        onMouseDown={(e) => e.stopPropagation()}
        disabled={disabled}
        title={cur.label}
        style={{ border: 'none', cursor: disabled ? 'default' : 'pointer', fontFamily: 'inherit' }}
      >
        <i />
        {cur.label}
        <span aria-hidden style={{ fontSize: 9, marginLeft: 2, opacity: 0.65 }}>
          ▾
        </span>
      </button>
      {open &&
        coords &&
        createPortal(
          <div
            ref={popRef}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
            style={{
              position: 'fixed',
              top: coords.top,
              left: coords.left,
              width: POP_W,
              zIndex: 1000,
              background: 'var(--surface)',
              border: '1px solid var(--line)',
              borderRadius: 6,
              padding: 4,
              boxShadow: '0 6px 18px rgba(0,0,0,0.16)',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              maxHeight: 320,
              overflowY: 'auto',
            }}
          >
            {options.map((v) => {
              const k = procStatusChip(v).kind
              return (
                <button
                  key={v}
                  type="button"
                  className={`chip ${k} mini`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSelect(v)
                    setOpen(false)
                  }}
                  onMouseDown={(e) => e.stopPropagation()}
                  style={{
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    justifyContent: 'flex-start',
                    width: '100%',
                  }}
                >
                  <i />
                  {v}
                </button>
              )
            })}
          </div>,
          document.body,
        )}
    </>
  )
}
