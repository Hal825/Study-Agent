import { useEffect, useRef } from 'react'
import { useAgentStore } from '../../stores/agentStore'
import { AGENT_STAGES } from '../../types'
import { Sparkles, CheckCircle2 } from 'lucide-react'

export default function AgentProgress() {
  const { currentStageIndex, isProcessing } = useAgentStore()
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest stage
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [currentStageIndex])

  return (
    <div className="animate-fade-in">
      {/* Central animation */}
      <div className="mb-8 flex flex-col items-center">
        <div className="relative mb-4">
          {/* Pulse rings */}
          <div className="absolute inset-0 animate-ping rounded-full bg-primary-100 opacity-30" style={{ width: 80, height: 80 }} />
          <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-primary-600 text-white shadow-lg shadow-primary-200">
            <Sparkles size={32} className="animate-pulse" />
          </div>
        </div>
        <h3 className="text-lg font-semibold text-gray-900">AI 智能体处理中</h3>
        <p className="text-sm text-gray-500">正在为您生成高质量的笔记内容</p>
      </div>

      {/* Stage list */}
      <div ref={containerRef} className="mx-auto max-w-md space-y-1">
        {AGENT_STAGES.map((stage, i) => {
          const isDone = i < currentStageIndex
          const isActive = i === currentStageIndex

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-500 ${
                isActive ? 'bg-primary-50 border border-primary-100' : ''
              }`}
            >
              {/* Status icon */}
              <div className="flex-shrink-0">
                {isDone ? (
                  <CheckCircle2 size={20} className="text-green-500" />
                ) : isActive ? (
                  <div className="flex h-5 w-5 items-center justify-center">
                    <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary-500" />
                  </div>
                ) : (
                  <div className="h-5 w-5 rounded-full border-2 border-gray-200" />
                )}
              </div>

              {/* Label */}
              <span
                className={`text-sm font-medium transition-colors ${
                  isDone
                    ? 'text-green-600'
                    : isActive
                      ? 'text-primary-700'
                      : 'text-gray-400'
                }`}
              >
                {stage.label}
              </span>

              {/* Typing dots when active */}
              {isActive && (
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
      <div className="mx-auto mt-6 max-w-md">
        <div className="h-1.5 overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-primary-500 transition-all duration-700 ease-out"
            style={{
              width: `${isProcessing ? ((currentStageIndex + 0.5) / AGENT_STAGES.length) * 100 : 0}%`,
            }}
          />
        </div>
      </div>
    </div>
  )
}
