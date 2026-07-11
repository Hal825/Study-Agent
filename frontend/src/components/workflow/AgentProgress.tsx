import { Sparkles } from 'lucide-react'

const ALL_STAGES = [
  '读取并理解内容...',
  '提取关键知识点...',
  '分析内容结构...',
  '确认模板选择...',
  '生成笔记内容...',
]

interface AgentProgressProps {
  currentStage: string
  stageIndex: number
  isConnected: boolean
}

export default function AgentProgress({ currentStage, stageIndex, isConnected }: AgentProgressProps) {
  if (!isConnected && !currentStage) return null

  return (
    <div className="animate-fade-in py-8">
      {/* Central indicator */}
      <div className="mb-8 flex flex-col items-center">
        <div className="relative mb-4">
          <div
            className="absolute inset-0 animate-pulse-soft rounded-full bg-accent-200/40"
            style={{ width: 64, height: 64 }}
          />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-100">
            <Sparkles size={24} className="text-primary-500" />
          </div>
        </div>
        <p className="text-sm font-medium text-ink-soft font-display">
          {currentStage || 'AI Agent 处理中...'}
        </p>
      </div>

      {/* Stage list */}
      <div className="mx-auto max-w-xs space-y-0.5">
        {ALL_STAGES.map((label, i) => {
          const done = i < stageIndex
          const active = i === stageIndex
          return (
            <div
              key={label}
              className={`flex items-center gap-3 rounded-xl px-4 py-2 transition-all duration-300 ${
                active ? 'bg-primary-50' : ''
              }`}
            >
              <div className="flex-shrink-0">
                {done ? (
                  <div className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path d="M2 5l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                ) : active ? (
                  <div className="h-2 w-2 rounded-full bg-primary-400 animate-pulse-soft" />
                ) : (
                  <div className="h-2 w-2 rounded-full bg-border" />
                )}
              </div>

              <span className={`text-xs font-medium transition-colors ${
                done ? 'text-emerald-600' : active ? 'text-primary-600' : 'text-ink-muted/30'
              }`}>
                {label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Progress bar */}
      <div className="mx-auto mt-6 max-w-xs">
        <div className="h-0.5 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-primary-400 transition-all duration-700 ease-out"
            style={{ width: `${Math.max(5, (stageIndex / ALL_STAGES.length) * 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
