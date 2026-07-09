import { useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  PenLine,
  GitGraph,
  Brain,
  Settings,
  GraduationCap,
  ChevronRight,
} from 'lucide-react'
import { TOOLS } from '../../types'

const ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'pen-line': PenLine,
  'git-graph': GitGraph,
  brain: Brain,
}

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <aside className="flex w-60 flex-col bg-ink text-ink-soft overflow-hidden select-none">
      {/* Logo — warm gold accent */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-white/6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-500/15 text-gold-400">
          <GraduationCap size={20} />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-white/90 tracking-tight">Study Agent</h1>
          <p className="text-2xs text-ink-muted mt-0.5">学习工作流编排</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-5 scrollbar-dark">
        {/* Dashboard */}
        <NavItem
          icon={<LayoutDashboard size={17} />}
          label="首页"
          active={location.pathname === '/'}
          onClick={() => navigate('/')}
        />

        {/* Section divider */}
        <div className="mt-6 mb-2 px-3">
          <p className="text-2xs font-semibold uppercase tracking-widest text-white/25">
            学习工具
          </p>
        </div>

        {/* Tools */}
        {TOOLS.map((tool) => {
          const IconComponent = ICONS[tool.icon]
          return (
            <NavItem
              key={tool.id}
              icon={IconComponent ? <IconComponent size={17} /> : undefined}
              label={tool.name}
              active={location.pathname === tool.path}
              available={tool.available}
              badge={tool.badge}
              onClick={() => tool.available && navigate(tool.path)}
            />
          )
        })}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Settings — bottom */}
        <NavItem
          icon={<Settings size={17} />}
          label="设置"
          active={false}
          available={false}
          badge="即将推出"
          onClick={() => {}}
        />
      </nav>

      {/* Version */}
      <div className="border-t border-white/6 px-5 py-3">
        <p className="text-2xs text-white/20">v0.2.0</p>
      </div>
    </aside>
  )
}

// ============================================================
// Nav item
// ============================================================
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
  const baseClass =
    'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150 mb-0.5'

  if (!available) {
    return (
      <button disabled className={`${baseClass} cursor-not-allowed text-white/20`}>
        {icon}
        <span className="flex-1 text-left">{label}</span>
        {badge && (
          <span className="rounded-full bg-white/5 px-1.5 py-0.5 text-2xs text-white/20">
            {badge}
          </span>
        )}
      </button>
    )
  }

  return (
    <button onClick={onClick} className={`${baseClass} group ${
      active
        ? 'bg-white/8 text-white shadow-sm ring-1 ring-white/10'
        : 'text-white/55 hover:bg-white/5 hover:text-white/80'
    }`}>
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {active && <ChevronRight size={12} className="text-gold-400" />}
    </button>
  )
}
