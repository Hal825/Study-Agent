import { useNavigate } from 'react-router-dom'
import {
  PenLine,
  GitGraph,
  Brain,
  ArrowRight,
  Sparkles,
  FileText,
  ChevronRight,
} from 'lucide-react'
import { TOOLS } from '../types'

const ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'pen-line': PenLine,
  'git-graph': GitGraph,
  brain: Brain,
}

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="mx-auto max-w-4xl px-8 py-12 animate-fade-in">
      {/* Hero — the thesis */}
      <div className="mb-14">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-gold-50 px-3 py-1 text-xs font-medium text-gold-700">
          <Sparkles size={12} />
          全新工作流模式
        </div>
        <h1 className="font-display text-4xl font-bold text-ink tracking-tight">
          将学习内容，
          <br />
          <span className="text-primary-500">转化为结构化知识</span>
        </h1>
        <p className="mt-4 max-w-lg text-ink-soft leading-relaxed">
          上传您的学习资料，选择合适的处理方式，由 AI 智能体自动完成知识整理。
          从内容到笔记，只需一次点击。
        </p>
      </div>

      {/* Workflow diagram — refined */}
      <div className="mb-14 rounded-2xl border border-border bg-surface p-6 shadow-card">
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-4">
          工作流
        </p>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {[
            { icon: FileText, label: '输入内容', color: 'bg-ink text-white' },
            { icon: null, label: '配置选项', color: 'bg-paper-dark text-ink-soft' },
            { icon: null, label: 'AI 处理', color: 'bg-paper-dark text-ink-soft' },
            { icon: null, label: '获得结果', color: 'bg-paper-dark text-ink-soft' },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center gap-3">
              <span className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${step.color}`}>
                <span className="text-2xs opacity-50">{i + 1}</span>
                {step.icon && <step.icon size={13} />}
                {step.label}
              </span>
              {i < arr.length - 1 && (
                <ChevronRight size={14} className="text-border" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Tool grid */}
      <h2 className="font-display text-xl font-semibold text-ink mb-5">
        选择学习工具
      </h2>
      <div className="grid gap-4 sm:grid-cols-3">
        {TOOLS.map((tool) => {
          const Icon = ICONS[tool.icon] ?? PenLine
          return (
            <button
              key={tool.id}
              disabled={!tool.available}
              onClick={() => tool.available && navigate(tool.path)}
              className={`group relative rounded-2xl border p-5 text-left transition-all duration-200 ${
                tool.available
                  ? 'border-border bg-surface shadow-card hover:shadow-card-hover hover:-translate-y-0.5 cursor-pointer'
                  : 'border-border-light bg-paper/50 cursor-not-allowed opacity-60'
              }`}
            >
              {tool.badge && (
                <span className="absolute right-4 top-4 rounded-full bg-paper-dark px-2 py-0.5 text-2xs text-ink-muted">
                  {tool.badge}
                </span>
              )}
              <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
                tool.available
                  ? 'bg-primary-50 text-primary-600 group-hover:bg-primary-100'
                  : 'bg-paper-dark text-ink-muted'
              }`}>
                <Icon size={20} />
              </div>
              <h3 className={`mb-1 text-sm font-semibold ${tool.available ? 'text-ink' : 'text-ink-muted'}`}>
                {tool.name}
              </h3>
              <p className="text-xs text-ink-muted leading-relaxed">{tool.description}</p>
              {tool.available && (
                <div className="mt-4 flex items-center gap-1 text-xs font-medium text-primary-600 opacity-0 group-hover:opacity-100 transition-opacity">
                  开始使用 <ArrowRight size={12} />
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
