import { Eye, EyeOff, Columns2 } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import type { PreviewMode } from '../../types'

const MODES: { mode: PreviewMode; icon: React.ComponentType<{ size?: number }>; title: string }[] = [
  { mode: 'chat', icon: EyeOff, title: '仅对话' },
  { mode: 'split', icon: Columns2, title: '分屏预览' },
  { mode: 'preview', icon: Eye, title: '仅预览' },
]

export default function PreviewToggle() {
  const previewMode = useChatStore((s) => s.previewMode)
  const setPreviewMode = useChatStore((s) => s.setPreviewMode)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const streamingContent = useChatStore((s) => s.streamingContent)
  const messages = useChatStore((s) => s.messages)

  // Only show toggle when there's something to preview
  const hasNoteContent = streamingContent.length > 0 || messages.some(m => m.type === 'markdown_note')
  if (!hasNoteContent && !isStreaming) return null

  const currentIndex = MODES.findIndex(m => m.mode === previewMode)
  const nextMode = MODES[(currentIndex + 1) % MODES.length]
  const NextIcon = nextMode.icon

  return (
    <button
      onClick={() => setPreviewMode(nextMode.mode)}
      className={`relative rounded-lg p-1.5 transition-all ${
        isStreaming
          ? 'text-primary-500 hover:bg-primary-50 animate-pulse-soft'
          : 'text-ink-muted/40 hover:text-ink-soft hover:bg-paper-dark'
      }`}
      title={nextMode.title}
    >
      <NextIcon size={15} />
      {previewMode !== 'chat' && (
        <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-primary-400" />
      )}
    </button>
  )
}
