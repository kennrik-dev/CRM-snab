export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty-state">
      <b>{title}</b>
      {hint && <div>{hint}</div>}
    </div>
  )
}
