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

const FORCE_OUTPUT_MS = 30_000 // 30 seconds before forcing partial output

const WELCOME_MESSAGE = `👋 你好！我是你的 AI 学习伴侣。

我可以帮你将学习资料转化为结构化的笔记。只需要：

1. **粘贴或上传**你的学习内容
2. 我会**分析内容**并给出设计建议
3. 你告诉我你的**偏好**（格式、重点、样式等）
4. 我为你**生成笔记**，你可以继续提出修改意见

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
  const [showSpinner, setShowSpinner] = useState(false)
  const [forceShowPartial, setForceShowPartial] = useState(false)
  const [spinnerText, setSpinnerText] = useState('AI 正在分析内容...')

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Manage spinner + 30s forced output timer
  useEffect(() => {
    if (isStreaming) {
      // Start tracking
      streamStartRef.current = Date.now()
      setShowSpinner(true)
      setForceShowPartial(false)

      // Determine spinner text based on phase
      if (phase === 'analyzing') setSpinnerText('AI 正在分析内容...')
      else if (phase === 'generating') setSpinnerText('AI 正在生成笔记...')
      else if (phase === 'revising') setSpinnerText('AI 正在修改笔记...')
      else setSpinnerText('AI 正在思考...')

      // Set up 30-second force-output timer
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
      // Clean up
      setShowSpinner(false)
      setForceShowPartial(false)
      streamStartRef.current = 0
      if (forceTimerRef.current) {
        clearInterval(forceTimerRef.current)
        forceTimerRef.current = null
      }
    }

    return () => {
      if (forceTimerRef.current) {
        clearInterval(forceTimerRef.current)
        forceTimerRef.current = null
      }
    }
  }, [isStreaming, phase])

  // Hide spinner when first content arrives
  useEffect(() => {
    if (streamingContent.length > 0 || messages.length > 0) {
      setShowSpinner(false)
    }
  }, [streamingContent, messages])

  // Handle sending: first message with content starts session,
  // subsequent messages go through sendMessage
  const handleSend = useCallback((text: string) => {
    if (phase === 'idle') {
      // First message: treat as content upload
      startSession(text)
    } else {
      sendMessage(text)
    }
  }, [phase, startSession, sendMessage])

  // Handle file upload
  const handleUpload = useCallback((content: string, _filename: string) => {
    startSession(content)
  }, [startSession])

  // Handle option card selection
  const handleOptionSelect = useCallback((optionId: string) => {
    const selections: SelectionsData = { template: optionId }
    const label = NOTE_TEMPLATES.find(t => t.id === optionId)?.name ?? optionId
    sendMessage(`选择格式：${label}`, selections)
  }, [sendMessage])

  const showWelcome = messages.length === 0 && phase === 'idle'

  return (
    <div className="flex h-full">
      {/* Chat area */}
      <div className={`flex flex-col ${previewMode === 'preview' ? 'hidden' : previewMode === 'split' ? 'w-1/2 border-r border-border' : 'flex-1'}`}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border bg-surface px-5 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-100 text-accent-600">
              <MessageCircle size={14} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-ink">AI 学习对话</h2>
              <p className="text-2xs text-ink-muted">
                {sessionId ? `会话 ${sessionId.slice(-8)}` : '新会话'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <PreviewToggle />
            <button
              onClick={reset}
              className="rounded-lg p-1.5 text-ink-muted/30 hover:text-ink-soft hover:bg-paper-dark transition-colors"
              title="重新开始"
            >
              <RotateCcw size={15} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-6">
          <div className="mx-auto max-w-3xl">
            {showWelcome ? (
              <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-100">
                  <Sparkles size={24} className="text-accent-500" />
                </div>
                <div className="max-w-md rounded-2xl border border-border bg-surface p-6 shadow-card text-left">
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

                {/* Spinner during streaming (before content arrives) */}
                {showSpinner && isStreaming && (
                  <div className="flex items-center gap-2.5 py-3 animate-fade-in">
                    <Loader2 size={16} className="animate-spin text-primary-400" />
                    <span className="text-xs text-ink-muted/60">{spinnerText}</span>
                  </div>
                )}

                {/* Forced partial output after 30s */}
                {forceShowPartial && streamingContent && (
                  <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/50 px-4 py-3">
                    <p className="text-2xs text-amber-600 mb-2">
                      ⏳ AI 还在生成中，以下为当前已生成的部分内容：
                    </p>
                    <div className="text-sm text-ink-soft whitespace-pre-wrap max-h-64 overflow-y-auto scrollbar-thin">
                      {streamingContent}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Error */}
            {error && (
              <div className="mx-auto max-w-sm rounded-2xl border border-red-100 bg-red-50 p-4 text-center my-4">
                <p className="text-xs text-red-600">{error}</p>
                <button
                  onClick={reset}
                  className="mt-2 text-xs font-medium text-red-500 hover:text-red-700 underline"
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
          onUpload={handleUpload}
        />
      </div>

      {/* Preview pane */}
      <NotePreview />
    </div>
  )
}
