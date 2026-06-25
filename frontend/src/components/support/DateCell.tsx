import { useState, type CSSProperties } from 'react'
import { dateRu } from '../../lib/format'

const inputStyle: CSSProperties = {
  border: '1px solid var(--line)',
  borderRadius: 4,
  padding: '2px 4px',
  fontFamily: 'inherit',
  fontSize: 12,
}

/** Дата в списке «В сопровождении»: показывается форматированным текстом `.dt`
 * (как в закупке), по клику (canEdit) превращается в `<input type=date>` для
 * правки — выбор даты коммитит PATCH и закрывает ввод. Пусто → «—».
 * Все клики stopPropagation, чтобы не сработал onRowClick (навигация в карточку). */
export function DateCell({
  value,
  canEdit,
  onCommit,
}: {
  value: string | null
  canEdit: boolean
  onCommit: (v: string | null) => void
}) {
  const [editing, setEditing] = useState(false)

  if (canEdit && editing) {
    return (
      <input
        type="date"
        autoFocus
        defaultValue={value ?? ''}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => {
          onCommit(e.target.value || null)
          setEditing(false)
        }}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setEditing(false)
        }}
        style={inputStyle}
      />
    )
  }

  return (
    <span
      className="dt"
      style={canEdit ? { cursor: 'pointer' } : undefined}
      onClick={
        canEdit
          ? (e) => {
              e.stopPropagation()
              setEditing(true)
            }
          : undefined
      }
      title={canEdit ? 'Нажмите, чтобы изменить' : undefined}
    >
      {dateRu(value)}
    </span>
  )
}
