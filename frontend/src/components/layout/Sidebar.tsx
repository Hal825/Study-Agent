import { useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  PenLine,
  GitGraph,
  Brain,
  Settings,
  GraduationCap,
} from 'lucide-react'
import { TOOLS, type ToolNavItem } from '../../types'

const NAV_ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  'pen-line': PenLine,
  'git-graph': GitGraph,
  brain: Brain,
}

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()

  const isActive = (path: string) => location.pathname === path

  return (
    <aside className="flex w-64 flex-col border-r border-gray-200 bg-white">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-100">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600 text-white">
          <GraduationCap size={20} />
        </div>
        <div>
          <h1 className="text-base font-bold text-gray-900 leading-tight">Study Agent</h1>
          <p className="text-xs text-gray-400 leading-tight">学习工作流编排</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
        {/* Dashboard */}
        <button
          onClick={() => navigate('/')}
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors mb-1 ${
            isActive('/')
              ? 'bg-primary-50 text-primary-700'
              : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
          }`}
        >
          <LayoutDashboard size={18} />
          首页
        </button>

        {/* Tool divider */}
        <p className="px-3 pt-5 pb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
          学习工具
        </p>

        {/* Tool items */}
        {TOOLS.map((tool) => (
          <ToolNavButton
            key={tool.id}
            tool={tool}
            isActive={isActive(tool.path)}
            onClick={() => tool.available && navigate(tool.path)}
          />
        ))}

        {/* Bottom: Settings (placeholder) */}
        <div className="mt-auto pt-4">
          <button
            disabled
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-300 transition-colors cursor-not-allowed"
          >
            <Settings size={18} />
            设置
            <span className="ml-auto text-xs text-gray-300">即将推出</span>
          </button>
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-100 px-5 py-3">
        <p className="text-xs text-gray-400">Study Agent v0.1.0</p>
      </div>
    </aside>
  )
}

function ToolNavButton({
  tool,
  isActive,
  onClick,
}: {
  tool: ToolNavItem
  isActive: boolean
  onClick: () => void
}) {
  const Icon = NAV_ICONS[tool.icon] ?? PenLine

  return (
    <button
      onClick={onClick}
      disabled={!tool.available}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors mb-1 ${
        !tool.available
          ? 'cursor-not-allowed text-gray-300'
          : isActive
            ? 'bg-primary-50 text-primary-700'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }`}
    >
      <Icon size={18} />
      {tool.name}
      {tool.badge && (
        <span className="ml-auto rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-400">
          {tool.badge}
        </span>
      )}
    </button>
  )
}
