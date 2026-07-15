import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Upload, Loader2, FileText } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

// ---- Constants ----
const BINARY_EXTENSIONS = ['.docx', '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20MB

function isBinaryFile(filename: string): boolean {
  const ext = '.' + filename.split('.').pop()?.toLowerCase()
  return BINARY_EXTENSIONS.includes(ext)
}

interface Props {
  onSend: (content: string) => void
  onUpload?: (content: string, filename: string) => void
  placeholder?: string
}

export default function ChatInput({ onSend, onUpload, placeholder }: Props) {
  const [text, setText] = useState('')
  const [uploading, setUploading] = useState(false)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const phase = useChatStore((s) => s.phase)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    }
  }, [text])

  const handleSend = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setText('')
  }, [text, isStreaming, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > MAX_FILE_SIZE) {
      alert('文件过大，上限为 20MB')
      if (fileRef.current) fileRef.current.value = ''
      return
    }

    setUploading(true)
    try {
      if (isBinaryFile(file.name)) {
        // Binary files: upload to backend
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch('/api/upload', { method: 'POST', body: formData })
        if (!res.ok) throw new Error('解析失败')
        const data = await res.json()
        if (data.content && onUpload) {
          onUpload(data.content, file.name)
        }
      } else {
        // Text files: read locally
        const text = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = (ev) => resolve(ev.target?.result as string)
          reader.onerror = () => reject(new Error('读取失败'))
          reader.readAsText(file)
        })
        if (text && onUpload) {
          onUpload(text, file.name)
        }
      }
    } catch (err: any) {
      alert(err.message || '文件处理失败')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }, [onUpload])

  const getPlaceholder = () => {
    if (placeholder) return placeholder
    if (isStreaming) return 'AI 正在回复中...'
    switch (phase) {
      case 'idle': return '在这里粘贴学习内容，或上传文件...'
      case 'design': return '回复 AI 的建议，如选择格式、指定重点主题...'
      case 'done':
      case 'result': return '告诉 AI 你想怎么修改笔记，或说"好的"完成...'
      default: return '输入你的消息...'
    }
  }

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-paper px-3 py-2 focus-within:border-primary-300 focus-within:ring-1 focus-within:ring-primary-100 transition-all">
          {/* Upload button */}
          <button
            onClick={() => fileRef.current?.click()}
            disabled={isStreaming || uploading}
            className="flex-shrink-0 rounded-lg p-1.5 text-ink-muted/40 hover:text-ink-soft hover:bg-paper-dark transition-colors disabled:opacity-30"
            title="上传文件"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          </button>

          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={getPlaceholder()}
            disabled={isStreaming}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-ink placeholder:text-ink-muted/30 outline-none disabled:opacity-50 max-h-40"
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!text.trim() || isStreaming}
            className={`flex-shrink-0 rounded-xl p-1.5 transition-all ${
              text.trim() && !isStreaming
                ? 'bg-primary-500 text-white hover:bg-primary-600'
                : 'text-ink-muted/20 cursor-not-allowed'
            }`}
          >
            <Send size={15} />
          </button>
        </div>

        <p className="mt-2 text-center text-2xs text-ink-muted/30">
          Enter 发送 · Shift+Enter 换行 · 支持粘贴文本和上传文件
        </p>

        <input
          ref={fileRef}
          type="file"
          accept=".md,.txt,.markdown,.json,.csv,.html,.xml,.yaml,.yml,.log,.docx,.pdf,.jpg,.jpeg,.png,.webp,.gif,.bmp"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>
    </div>
  )
}
