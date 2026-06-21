import type { ReactNode } from 'react'

export function FilterBar({
  children,
  actions,
  className,
}: {
  children: ReactNode
  actions?: ReactNode
  className?: string
}) {
  const cls = `filter-bar ${className ?? ''}`.trim()
  return (
    <div className={cls}>
      {children}
      <span className="sp" />
      {actions}
    </div>
  )
}
