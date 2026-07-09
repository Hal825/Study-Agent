import { useNavigate } from 'react-router-dom'
import {
  PenLine,
  GitGraph,
  Brain,
  ArrowRight,
  Sparkles,
  GraduationCap,
} from 'lucide-react'
import { TOOLS } from '../types'

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'pen-line': PenLine,
  'git-graph': GitGraph,
  brain: Brain,
}

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="mx-auto max-w-4xl px-6 py-10 animate-fade-in">
      {/* Hero */}
      <div className="mb-12 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-600 text-white shadow-lg shadow-primary-200">
          <GraduationCap size={28} />
        </div>
        <h1 className="text-3xl font-bold text-gray-900">Study Agent</h1>
        <p className="mt-2 text-gray-500">
          基于 AI 智能体的学习工作流编排平台
          <br />
          <span className="text-sm">
            上传内容，选择处理方式，让 AI 帮你完成知识整理
          </span>
        </p>
      </div>

      {/* Workflow hint */}
      <div className="mb-10 rounded-2xl border border-primary-100 bg-primary-50/50 p-5">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={16} className="text-primary-500" />
          <span className="text-sm font-semibold text-primary-700">工作流模式</span>
        </div>
        <div className="flex items-center justify-center gap-3 text-sm">
          {['📄 输入内容', '⚙️ 配置选项', '🤖 AI 处理', '✨ 获得结果'].map((label, i, arr) => (
            <div key={label} className="flex items-center gap-3">
              <span className={`rounded-full px-3 py-1.5 font-medium ${
                i === 0 ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 border border-gray-200'
              }`}>
                {label}
              </span>
              {i < arr.length - 1 && <ArrowRight size={14} className="text-gray-300" />}
            </div>
          ))}
        </div>
      </div>

      {/* Tool cards */}
      <h2 className="mb-5 text-lg font-semibold text-gray-900">选择学习工具</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map((tool) => {
          const Icon = ICON_MAP[tool.icon] ?? PenLine
          const isAvailable = tool.available

          return (
            <button
              key={tool.id}
              disabled={!isAvailable}
              onClick={() => isAvailable && navigate(tool.path)}
              className={`group relative rounded-2xl border p-6 text-left transition-all duration-200 ${
                isAvailable
                  ? 'border-gray-200 bg-white hover:border-primary-300 hover:shadow-lg hover:shadow-primary-100/50 hover:-translate-y-0.5 cursor-pointer'
                  : 'border-gray-100 bg-gray-50/50 cursor-not-allowed opacity-70'
              }`}
            >
              {tool.badge && (
                <span className="absolute right-4 top-4 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-400">
                  {tool.badge}
                </span>
              )}
              <div
                className={`mb-3 flex h-11 w-11 items-center justify-center rounded-xl transition-colors ${
                  isAvailable
                    ? 'bg-primary-50 text-primary-600 group-hover:bg-primary-100'
                    : 'bg-gray-100 text-gray-400'
                }`}
              >
                <Icon size={22} />
              </div>
              <h3 className={`mb-1.5 text-base font-semibold ${isAvailable ? 'text-gray-900' : 'text-gray-400'}`}>
                {tool.name}
              </h3>
              <p className="text-sm text-gray-500 leading-relaxed">{tool.description}</p>
              {isAvailable && (
                <div className="mt-4 flex items-center gap-1 text-sm font-medium text-primary-600 opacity-0 group-hover:opacity-100 transition-opacity">
                  开始使用 <ArrowRight size={14} />
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
