import { useNavigate } from 'react-router-dom'
import { MessageCircle, GitGraph, Brain, ArrowRight, Sparkles } from 'lucide-react'
import { TOOLS } from '../types'

const ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  'message-circle': MessageCircle,
  'git-graph': GitGraph,
  brain: Brain,
}

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="mx-auto max-w-4xl px-8 py-16 animate-fade-in">
      {/* Hero */}
      <div className="mb-16 text-center">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-accent-50 px-3.5 py-1 text-xs font-medium text-accent-600">
          <Sparkles size={12} />
          全新 AI Agent 驱动
        </div>
        <h1 className="font-display text-4xl font-bold text-ink tracking-tight leading-tight">
          将学习内容
          <br />
          <span className="text-primary-500">转化为结构化知识</span>
        </h1>
        <p className="mt-4 mx-auto max-w-md text-ink-soft leading-relaxed">
          上传学习资料，AI Agent 自动完成内容解析、知识点提取与结构化笔记生成。
          从内容到笔记，只需一次上传。
        </p>
      </div>

      {/* Tool grid */}
      <h2 className="font-display text-lg font-semibold text-ink mb-5 text-center">
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
              className={`group relative rounded-3xl border p-6 text-left transition-all duration-200 ${
                tool.available
                  ? 'border-border bg-surface shadow-card hover:shadow-card-hover hover:-translate-y-0.5 cursor-pointer'
                  : 'border-border/50 bg-paper/50 cursor-not-allowed opacity-50'
              }`}
            >
              {tool.badge && (
                <span className="absolute right-5 top-5 rounded-lg bg-paper-dark px-2.5 py-0.5 text-2xs text-ink-muted">
                  {tool.badge}
                </span>
              )}
              <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-2xl transition-colors ${
                tool.available
                  ? 'bg-primary-50 text-primary-500 group-hover:bg-primary-100'
                  : 'bg-paper-dark text-ink-muted'
              }`}>
                <Icon size={20} />
              </div>
              <h3 className={`mb-1 text-sm font-semibold ${tool.available ? 'text-ink' : 'text-ink-muted'}`}>
                {tool.name}
              </h3>
              <p className="text-xs text-ink-muted leading-relaxed">{tool.description}</p>
              {tool.available && (
                <div className="mt-5 flex items-center gap-1 text-xs font-medium text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity">
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
