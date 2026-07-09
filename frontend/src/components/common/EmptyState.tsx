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
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 text-gray-400">
        {icon}
      </div>
      <h3 className="mb-2 text-lg font-semibold text-gray-700">{title}</h3>
      <p className="mb-6 max-w-sm text-center text-sm text-gray-500">{description}</p>
      {action}
    </div>
  )
}
