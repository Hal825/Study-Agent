import { useCallback, useEffect, useRef, useState } from 'react'
import { RotateCcw, MessageCircle, Sparkles, Loader2 } from 'lucide-react'
import { useChatStore } from '../stores/chatStore'
import { useChatSSE } from '../hooks/useChatSSE'
import { NOTE_TEMPLATES } from '../types'
import type { SelectionsData } from '../types'
import ChatMessage from '../components/chat/ChatMessage'
import ChatInput from '../components/chat/ChatInput'
import NotePreview from '../components/chat/NotePreview'
import PreviewToggle from '../components/chat/PreviewToggle'

const FORCE_OUTPUT_MS = 30_000

const PHASE_STYLES: Record<string, { label: string; badgeClass: string; icon: string }> = {
  analyzing:  { label: '分析内容',   badgeClass: 'bg-sky-50 text-sky-700',    icon: '🔍' },
  design:     { label: '设计方案',   badgeClass: 'bg-violet-50 text-violet-700', icon: '🎨' },
  generating: { label: '生成笔记',   badgeClass: 'bg-emerald-50 text-emerald-700',icon: '✍️' },
  revising:   { label: '修改笔记',   badgeClass: 'bg-accent-50 text-accent-700', icon: '🔧' },
  done:       { label: '完成',       badgeClass: 'bg-emerald-50 text-emerald-700',icon: '✅' },
}

const QUICK_STARTS = [
  { icon: '📄', label: '粘贴文本', desc: '直接粘贴学习资料', placeholder: '在这里粘贴你的学习内容，我会帮你整理成结构化的笔记...' },
  { icon: '📁', label: '上传文件', desc: '支持 MD/TXT/PDF/DOCX', placeholder: '' },
  { icon: '🎯', label: '选择格式', desc: '大纲/摘要/康奈尔/问答', placeholder: '' },
]

const WELCOME_MESSAGE = `👋 你好！我是你的 **AI 学习伴侣**。

我可以帮你将学习资料转化为结构化笔记：

1. **📋 上传内容** — 粘贴文本或上传文件（支持 MD、TXT、PDF、DOCX、图片）
2. **🔍 智能分析** — AI 自动解析内容结构，识别核心主题
3. **🎨 定制格式** — 选择大纲笔记、详细摘要、康奈尔笔记或问答格式
4. **✨ 实时生成** — 流式生成笔记，支持实时预览和后续修改

现在，请把你的学习内容发送给我吧！`

export default function ChatPage() {
  const messages = useChatStore((s) => s.messages)
  const sessionId = useChatStore((s) => s.sessionId)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const phase = useChatStore((s) => s.phase)
  const previewMode = useChatStore((s) => s.previewMode)
  const streamingContent = useChatStore((s) => s.streamingContent)
  const error = useChatStore((s) => s.error)
  const { startSession, sendMessage, reset } = useChatSSE()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const streamStartRef = useRef<number>(0)
  const forceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const analyzeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [showSpinner, setShowSpinner] = useState(false)
  const [forceShowPartial, setForceShowPartial] = useState(false)
  const [spinnerDetail, setSpinnerDetail] = useState('')

  const ANALYZE_STEPS = [
    '正在解析内容结构...',
    '正在提取核心主题与概念...',
    '正在分析知识关联与层级...',
    '正在设计笔记框架方案...',
  ]

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Manage spinner + forced output timer + analyze step cycling
  useEffect(() => {
    if (isStreaming) {
      streamStartRef.current = Date.now()
      setShowSpinner(true)
      setForceShowPartial(false)

      // Cycle through analyze steps during 'analyzing' phase
      if (phase === 'analyzing') {
        let stepIndex = 0
        setSpinnerDetail(ANALYZE_STEPS[0])
        analyzeTimerRef.current = setInterval(() => {
          stepIndex = (stepIndex + 1) % ANALYZE_STEPS.length
          setSpinnerDetail(ANALYZE_STEPS[stepIndex])
        }, 2500)
      }

      forceTimerRef.current = setInterval(() => {
        const elapsed = Date.now() - streamStartRef.current
        if (elapsed >= FORCE_OUTPUT_MS) {
          setForceShowPartial(true)
          if (forceTimerRef.current) {
            clearInterval(forceTimerRef.current)
            forceTimerRef.current = null
          }
        }
      }, 1000)
    } else {
      setShowSpinner(false)
      setForceShowPartial(false)
      setSpinnerDetail('')
      streamStartRef.current = 0
      if (forceTimerRef.current) {
        clearInterval(forceTimerRef.current)
        forceTimerRef.current = null
      }
      if (analyzeTimerRef.current) {
        clearInterval(analyzeTimerRef.current)
        analyzeTimerRef.current = null
      }
    }

    return () => {
      if (forceTimerRef.current) {
        clearInterval(forceTimerRef.current)
        forceTimerRef.current = null
      }
      if (analyzeTimerRef.current) {
        clearInterval(analyzeTimerRef.current)
        analyzeTimerRef.current = null
      }
    }
  }, [isStreaming, phase])

  // Hide spinner when first content arrives
  useEffect(() => {
    if (streamingContent.length > 0 || messages.length > 0) {
      setShowSpinner(false)
    }
  }, [streamingContent, messages])

  const handleSend = useCallback((text: string, fileName?: string, fileSize?: number) => {
    if (phase === 'idle') {
      startSession(text, fileName, fileSize)
    } else {
      const fileInfo = fileName ? { name: fileName, size: fileSize ?? 0 } : undefined
      sendMessage(text, undefined, fileInfo)
    }
  }, [phase, startSession, sendMessage])

  const handleOptionSelect = useCallback((optionId: string) => {
    const selections: SelectionsData = { template: optionId }
    const label = NOTE_TEMPLATES.find(t => t.id === optionId)?.name ?? optionId
    sendMessage(`选择格式：${label}`, selections)
  }, [sendMessage])

  const showWelcome = messages.length === 0 && phase === 'idle'
  const phaseStyle = PHASE_STYLES[phase] ?? { label: '思考中', badgeClass: 'bg-primary-50 text-primary-700', icon: '💭' }

  return (
    <div className="flex h-full">
      {/* ── Chat area ── */}
      <div className={`flex flex-col ${
        previewMode === 'preview' ? 'hidden' :
        previewMode === 'split' ? 'w-1/2 border-r border-border' : 'flex-1'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border bg-surface/90 backdrop-blur-sm px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-100 text-accent-600">
              <MessageCircle size={16} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-ink">AI 学习对话</h2>
              <p className="text-xs text-ink-muted">
                {sessionId ? `会话 ${sessionId.slice(-8)}` : '新会话'}
              </p>
            </div>
            {/* Phase badge */}
            {phase !== 'idle' && (
              <span className={`ml-2 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${phaseStyle.badgeClass}`}>
                <span className="text-xs">{phaseStyle.icon}</span>
                {phaseStyle.label}
                {isStreaming && (
                  <span className="flex gap-0.5 ml-1">
                    <span className="typing-dot" style={{width:4,height:4}} />
                    <span className="typing-dot" style={{width:4,height:4}} />
                    <span className="typing-dot" style={{width:4,height:4}} />
                  </span>
                )}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <PreviewToggle />
            <button
              onClick={reset}
              className="rounded-lg p-1.5 text-ink-muted/40 hover:text-ink-soft hover:bg-paper-dark transition-colors"
              title="重新开始"
            >
              <RotateCcw size={15} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-6">
          <div className="mx-auto max-w-4xl">
            {showWelcome ? (
              /* ── Welcome Screen ── */
              <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
                <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-100 shadow-sm">
                  <Sparkles size={28} className="text-accent-500" />
                </div>
                <h1 className="font-display text-2xl font-bold text-ink mb-2">
                  开始学习之旅
                </h1>
                <p className="text-base text-ink-muted mb-8">
                  上传学习内容，AI 帮你生成结构化笔记
                </p>

                {/* Quick start cards */}
                <div className="grid gap-3 sm:grid-cols-3 mb-10 w-full max-w-2xl">
                  {QUICK_STARTS.map((item) => (
                    <div
                      key={item.label}
                      className="rounded-2xl border border-border bg-surface p-4 text-center hover:border-accent-200 hover:shadow-card-hover transition-all duration-200"
                    >
                      <span className="text-2xl mb-2 block">{item.icon}</span>
                      <h3 className="text-sm font-semibold text-ink mb-0.5">{item.label}</h3>
                      <p className="text-xs text-ink-muted">{item.desc}</p>
                    </div>
                  ))}
                </div>

                {/* Welcome message card */}
                <div className="max-w-xl rounded-2xl border border-border/80 bg-surface p-6 shadow-card text-left">
                  <p className="text-sm text-ink-soft leading-relaxed whitespace-pre-wrap">
                    {WELCOME_MESSAGE}
                  </p>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    onOptionSelect={handleOptionSelect}
                  />
                ))}

                {/* Streaming indicator */}
                {showSpinner && isStreaming && (
                  <div className="flex items-start gap-3 py-4 animate-fade-in">
                    <div className="flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-xl bg-accent-100 mt-0.5">
                      <Loader2 size={15} className="animate-spin text-accent-500" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-ink-soft">{phaseStyle.label}</span>
                        <span className="flex gap-1">
                          <span className="typing-dot" />
                          <span className="typing-dot" />
                          <span className="typing-dot" />
                        </span>
                      </div>
                      {spinnerDetail && (
                        <p className="text-xs text-ink-muted mt-1 animate-fade-in">{spinnerDetail}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Forced partial output */}
                {forceShowPartial && streamingContent && (
                  <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/60 px-5 py-4">
                    <p className="text-xs text-amber-600 mb-2 font-medium">
                      ⏳ AI 还在生成中，以下为当前已生成的部分内容：
                    </p>
                    <div className="text-sm text-ink-soft whitespace-pre-wrap max-h-72 overflow-y-auto scrollbar-thin leading-relaxed">
                      {streamingContent}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Error */}
            {error && (
              <div className="mx-auto max-w-md rounded-2xl border border-rose-200 bg-rose-50 p-5 text-center my-4">
                <p className="text-sm text-rose-600">{error}</p>
                <button
                  onClick={reset}
                  className="mt-3 text-sm font-medium text-rose-600 hover:text-rose-700 underline underline-offset-2"
                >
                  重新开始
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
        />
      </div>

      {/* Preview pane */}
      <NotePreview />
    </div>
  )
}
