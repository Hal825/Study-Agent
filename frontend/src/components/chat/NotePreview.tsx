import { Eye, EyeOff, Columns2 } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import MarkdownRenderer from '../common/MarkdownRenderer'

export default function NotePreview() {
  const streamingContent = useChatStore((s) => s.streamingContent)
  const previewMode = useChatStore((s) => s.previewMode)
  const setPreviewMode = useChatStore((s) => s.setPreviewMode)
  const isStreaming = useChatStore((s) => s.isStreaming)

  // Get the last markdown_note message content as fallback
  const messages = useChatStore((s) => s.messages)
  const lastNote = [...messages].reverse().find(m => m.type === 'markdown_note')
  const displayContent = streamingContent || lastNote?.content || ''

  if (previewMode === 'chat') return null

  const isFullPreview = previewMode === 'preview'

  return (
    <div className={`flex flex-col border-l border-border bg-surface ${isFullPreview ? 'flex-1' : 'w-1/2'}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <Eye size={15} className="text-ink-muted" />
          <span className="text-sm font-medium text-ink-soft">实时预览</span>
          {isStreaming && (
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft" />
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPreviewMode('split')}
            className={`rounded-lg p-1.5 transition-colors ${
              previewMode === 'split'
                ? 'bg-primary-50 text-primary-600'
                : 'text-ink-muted/40 hover:text-ink-soft'
            }`}
            title="分屏视图"
          >
            <Columns2 size={13} />
          </button>
          <button
            onClick={() => setPreviewMode('preview')}
            className={`rounded-lg p-1.5 transition-colors ${
              previewMode === 'preview'
                ? 'bg-primary-50 text-primary-600'
                : 'text-ink-muted/40 hover:text-ink-soft'
            }`}
            title="仅预览"
          >
            <Eye size={13} />
          </button>
          <button
            onClick={() => setPreviewMode('chat')}
            className="rounded-lg p-1.5 text-ink-muted/40 hover:text-ink-soft transition-colors"
            title="关闭预览"
          >
            <EyeOff size={13} />
          </button>
        </div>
      </div>

      {/* Preview content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {displayContent ? (
          <MarkdownRenderer content={displayContent} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-ink-muted/30">
            <Eye size={32} className="mb-3" />
            <p className="text-xs">笔记预览将在此显示</p>
            <p className="text-xs mt-1">生成过程中会实时更新</p>
          </div>
        )}
      </div>
    </div>
  )
}
