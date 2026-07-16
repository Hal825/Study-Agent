import { useState } from 'react'
import { GraduationCap, User, ChevronDown, ChevronRight, FileText, FileImage, FileArchive } from 'lucide-react'
import type { ChatMessage as ChatMessageType } from '../../types'
import MarkdownRenderer from '../common/MarkdownRenderer'
import DesignFrameworkCard from './DesignFrameworkCard'
import OptionCards from './OptionCards'

interface Props {
  message: ChatMessageType
  onOptionSelect?: (optionId: string) => void
}

// ── File icon helpers ──
function getFileTypeInfo(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'svg'].includes(ext)) {
    return { icon: FileImage, color: 'bg-violet-50 text-violet-500 border-violet-200', label: '图片' }
  }
  if (ext === 'pdf') {
    return { icon: FileArchive, color: 'bg-rose-50 text-rose-500 border-rose-200', label: 'PDF' }
  }
  if (ext === 'docx' || ext === 'doc') {
    return { icon: FileText, color: 'bg-sky-50 text-sky-500 border-sky-200', label: 'DOCX' }
  }
  if (['md', 'txt', 'markdown'].includes(ext)) {
    return { icon: FileText, color: 'bg-emerald-50 text-emerald-500 border-emerald-200', label: ext.toUpperCase() }
  }
  return { icon: FileText, color: 'bg-paper-dark text-ink-muted border-border', label: ext || 'FILE' }
}

function formatSize(bytes?: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── Thinking process display ──
function ThinkingChain({ steps }: { steps: string[] }) {
  const [open, setOpen] = useState(false)

  if (!steps || steps.length === 0) return null

  return (
    <div className="thinking-chain mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink-soft transition-colors"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>思考过程 ({steps.length} 步)</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 border-l-2 border-accent-200 pl-3 py-0.5">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-ink-muted">
              <span className="text-accent-400 mt-0.5 flex-shrink-0 text-xs">•</span>
              <span className="leading-relaxed">{step}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── File attachment card ──
function FileAttachment({ name, size }: { name: string; size?: number }) {
  const info = getFileTypeInfo(name)
  const Icon = info.icon

  return (
    <div className={`file-card inline-flex items-center gap-2.5 rounded-xl border px-3 py-2 mt-2 ${info.color}`}>
      <Icon size={15} />
      <div>
        <p className="text-xs font-medium text-ink leading-tight truncate max-w-[180px]">{name}</p>
        {size && <p className="text-xs text-ink-muted/50">{formatSize(size)}</p>}
      </div>
    </div>
  )
}

export default function ChatMessage({ message, onOptionSelect }: Props) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const isProgress = message.type === 'progress'

  // Progress messages: subtle inline status indicator (streaming feedback)
  if (isProgress) {
    return (
      <div className="flex items-center gap-2.5 py-1.5 msg-enter">
        <div className="flex-shrink-0 h-5 w-5 flex items-center justify-center rounded-full bg-emerald-50">
          <span className="text-emerald-500 text-xs">✓</span>
        </div>
        <span className="text-xs text-ink-muted">{message.content}</span>
      </div>
    )
  }

  // System messages are rendered differently
  if (isSystem) {
    return (
      <div className="flex justify-center mb-5 msg-enter">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-paper-dark px-3 py-1 text-xs text-ink-muted">
          {message.content}
        </span>
      </div>
    )
  }

  return (
    <div className={`flex gap-3 mb-6 msg-enter ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 flex h-9 w-9 items-center justify-center rounded-xl ${
        isUser
          ? 'bg-primary-100 text-primary-500'
          : 'bg-accent-100 text-accent-600'
      }`}>
        {isUser ? <User size={16} /> : <GraduationCap size={16} />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[78%] min-w-0 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Role label */}
        <p className={`mb-1 text-xs font-medium ${isUser ? 'text-right text-primary-500' : 'text-accent-600'}`}>
          {isUser ? '你' : 'AI 学习伴侣'}
        </p>

        <div className={`rounded-2xl px-5 py-3.5 text-base leading-relaxed ${
          isUser
            ? 'bg-primary-50 text-ink rounded-tr-md'
            : 'bg-surface border border-border text-ink-soft rounded-tl-md shadow-card'
        }`}>
          {message.type === 'markdown_note' ? (
            <div className="max-h-[32rem] overflow-y-auto scrollbar-thin">
              <MarkdownRenderer content={message.content} />
            </div>
          ) : message.type === 'design_framework' ? (
            <DesignFrameworkCard data={message.data as any} />
          ) : message.type === 'option_cards' ? (
            <OptionCards
              data={message.data as any}
              onSelect={onOptionSelect}
            />
          ) : (
            <>
              <p className="whitespace-pre-wrap">{message.content}</p>
              {/* Show file attachment if message has uploaded file info */}
              {message.fileName && (
                <FileAttachment name={message.fileName} size={message.fileSize} />
              )}
            </>
          )}

          {/* Thinking process (assistant only) */}
          {!isUser && message.thinkingSteps && message.thinkingSteps.length > 0 && (
            <ThinkingChain steps={message.thinkingSteps} />
          )}
        </div>

        {/* Timestamp */}
        <p className={`mt-1.5 text-xs text-ink-muted/40 ${isUser ? 'text-right' : ''}`}>
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  )
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
