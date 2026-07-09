import { useEffect, useRef } from 'react'
import { useAgentStore } from '../../stores/agentStore'
import { AGENT_STAGES } from '../../types'
import { Sparkles, CheckCircle2 } from 'lucide-react'

export default function AgentProgress() {
  const { currentStageIndex } = useAgentStore()
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [currentStageIndex])

  return (
    <div className="animate-fade-in py-8">
      {/* Central indicator */}
      <div className="mb-10 flex flex-col items-center">
        <div className="relative mb-4">
          <div className="absolute inset-0 animate-ping rounded-full bg-gold-200/30" style={{ width: 72, height: 72 }} />
          <div className="relative flex h-[72px] w-[72px] items-center justify-center rounded-2xl bg-ink shadow-lg">
            <Sparkles size={28} className="text-gold-400" />
          </div>
        </div>
        <h3 className="text-base font-semibold text-ink font-display">AI 智能体处理中</h3>
        <p className="mt-1 text-sm text-ink-muted">正在为您生成高质量的学习笔记</p>
      </div>

      {/* Stages */}
      <div ref={containerRef} className="mx-auto max-w-sm space-y-0.5">
        {AGENT_STAGES.map((stage, i) => {
          const done = i < currentStageIndex
          const active = i === currentStageIndex

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-3 rounded-xl px-4 py-2.5 transition-all duration-300 ${
                active ? 'bg-primary-50 border border-primary-100' : ''
              }`}
            >
              <div className="flex-shrink-0">
                {done ? (
                  <CheckCircle2 size={17} className="text-emerald-500" />
                ) : active ? (
                  <div className="flex h-4 w-4 items-center justify-center">
                    <div className="h-2 w-2 animate-pulse rounded-full bg-primary-500" />
                  </div>
                ) : (
                  <div className="h-4 w-4 rounded-full border-2 border-border" />
                )}
              </div>

              <span className={`text-sm font-medium transition-colors ${
                done ? 'text-emerald-600' : active ? 'text-primary-700' : 'text-ink-muted/40'
              }`}>
                {stage.label}
              </span>

              {active && (
                <span className="ml-auto flex gap-0.5">
                  <span className="animate-pulse-dot h-1 w-1 rounded-full bg-primary-400" style={{ animationDelay: '0s' }} />
                  <span className="animate-pulse-dot h-1 w-1 rounded-full bg-primary-400" style={{ animationDelay: '0.2s' }} />
                  <span className="animate-pulse-dot h-1 w-1 rounded-full bg-primary-400" style={{ animationDelay: '0.4s' }} />
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Progress bar */}
      <div className="mx-auto mt-8 max-w-sm">
        <div className="h-1 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-ink transition-all duration-700 ease-out"
            style={{ width: `${((currentStageIndex + 0.5) / AGENT_STAGES.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  )
}
