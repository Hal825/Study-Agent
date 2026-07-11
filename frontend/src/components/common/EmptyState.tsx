import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-paper-dark text-ink-muted/30">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-ink-soft mb-1">{title}</h3>
      <p className="text-xs text-ink-muted mb-5 max-w-xs text-center leading-relaxed">{description}</p>
      {action}
    </div>
  )
}
