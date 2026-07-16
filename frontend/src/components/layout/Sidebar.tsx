import { useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageCircle,
  GitGraph,
  Brain,
  Settings,
  GraduationCap,
} from 'lucide-react'
import { TOOLS } from '../../types'

const ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  'message-circle': MessageCircle,
  'git-graph': GitGraph,
  brain: Brain,
}

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <aside className="flex w-48 flex-col border-r border-border bg-surface select-none">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5">
        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-accent-100 text-accent-600">
          <GraduationCap size={16} />
        </div>
        <div className="min-w-0">
          <h1 className="text-sm font-semibold text-ink tracking-tight truncate">Study Agent</h1>
          <p className="text-xs text-ink-muted mt-0.5">AI 学习伴侣</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-sidebar">
        <NavItem
          icon={<LayoutDashboard size={16} />}
          label="首页"
          active={location.pathname === '/'}
          onClick={() => navigate('/')}
        />

        {/* Section label */}
        <div className="mt-6 mb-1.5 px-2.5">
          <p className="text-xs font-medium uppercase tracking-wider text-ink-muted/50">
            工具
          </p>
        </div>

        {TOOLS.map((tool) => {
          const IconComponent = ICONS[tool.icon]
          return (
            <NavItem
              key={tool.id}
              icon={IconComponent ? <IconComponent size={16} /> : undefined}
              label={tool.name}
              active={location.pathname === tool.path}
              available={tool.available}
              badge={tool.badge}
              onClick={() => tool.available && navigate(tool.path)}
            />
          )
        })}

        <div className="flex-1" />

        <NavItem
          icon={<Settings size={16} />}
          label="设置"
          active={false}
          available={false}
          badge="近期"
          onClick={() => {}}
        />
      </nav>

      {/* Version */}
      <div className="border-t border-border px-4 py-3">
        <p className="text-xs text-ink-muted/40">v0.3.0</p>
      </div>
    </aside>
  )
}

function NavItem({
  icon,
  label,
  active = false,
  available = true,
  badge,
  onClick,
}: {
  icon?: React.ReactNode
  label: string
  active?: boolean
  available?: boolean
  badge?: string
  onClick: () => void
}) {
  if (!available) {
    return (
      <button disabled className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-ink-muted/30 cursor-not-allowed mb-0.5 transition-colors">
        {icon}
        <span className="flex-1 text-left">{label}</span>
        {badge && (
          <span className="rounded-md bg-paper-dark px-1.5 py-0.5 text-xs text-ink-muted/40">
            {badge}
          </span>
        )}
      </button>
    )
  }

  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium mb-0.5 transition-all duration-150 ${
        active
          ? 'bg-primary-50 text-primary-700'
          : 'text-ink-soft hover:bg-paper-dark hover:text-ink'
      }`}
    >
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {badge && (
        <span className="rounded-md bg-accent-100 px-1.5 py-0.5 text-xs text-accent-700">
          {badge}
        </span>
      )}
    </button>
  )
}
