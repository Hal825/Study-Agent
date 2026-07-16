import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Loader2, FileText, FileImage, FileArchive, X, Paperclip } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'

// ── Constants ──
const BINARY_EXTENSIONS = ['.docx', '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
const MAX_FILE_SIZE = 20 * 1024 * 1024 // 20MB

function isBinaryFile(filename: string): boolean {
  const ext = '.' + filename.split('.').pop()?.toLowerCase()
  return BINARY_EXTENSIONS.includes(ext)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── File type info for styling ──
interface FileTypeInfo {
  icon: React.ComponentType<{ size?: number }>
  bg: string
  text: string
  border: string
  label: string
}

function getFileTypeInfo(filename: string): FileTypeInfo {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'svg'].includes(ext)) {
    return { icon: FileImage, bg: 'bg-violet-50', text: 'text-violet-600', border: 'border-violet-200', label: '图片' }
  }
  if (ext === 'pdf') {
    return { icon: FileArchive, bg: 'bg-rose-50', text: 'text-rose-600', border: 'border-rose-200', label: 'PDF' }
  }
  if (ext === 'docx' || ext === 'doc') {
    return { icon: FileText, bg: 'bg-sky-50', text: 'text-sky-600', border: 'border-sky-200', label: 'DOCX' }
  }
  if (['md', 'txt', 'markdown'].includes(ext)) {
    return { icon: FileText, bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-200', label: ext.toUpperCase() }
  }
  if (['json', 'csv', 'xml', 'yaml', 'yml', 'html'].includes(ext)) {
    return { icon: FileText, bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-200', label: ext.toUpperCase() }
  }
  return { icon: FileText, bg: 'bg-paper-dark', text: 'text-ink-muted', border: 'border-border', label: ext.toUpperCase() }
}

// ── Pending file entry ──
interface PendingFile {
  id: string
  name: string
  size: number
  status: 'pending' | 'parsing' | 'done' | 'error'
  content?: string
  error?: string
}

interface Props {
  onSend: (content: string, fileName?: string, fileSize?: number) => void
  placeholder?: string
}

export default function ChatInput({ onSend, placeholder }: Props) {
  const [text, setText] = useState('')
  const [uploading, setUploading] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const isStreaming = useChatStore((s) => s.isStreaming)
  const phase = useChatStore((s) => s.phase)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 200) + 'px'
    }
  }, [text])

  // Remove a pending file
  const removeFile = useCallback((id: string) => {
    setPendingFiles(prev => prev.filter(f => f.id !== id))
  }, [])

  const handleSend = useCallback(() => {
    const trimmed = text.trim()
    const hasFileContent = pendingFiles.some(f => f.status === 'done')
    if ((!trimmed && !hasFileContent) || isStreaming) return

    // Priority: file content (if available), otherwise text
    const firstFile = pendingFiles.find(f => f.status === 'done')
    if (firstFile?.content) {
      // Send file content as the message; include user text as context if present
      const msg = trimmed ? `${trimmed}\n\n---\n${firstFile.content}` : firstFile.content
      onSend(msg, firstFile.name, firstFile.size)
    } else {
      onSend(trimmed)
    }
    setText('')
    setPendingFiles([])
  }, [text, isStreaming, pendingFiles, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  // Process a single file
  const processFile = useCallback(async (file: File) => {
    if (file.size > MAX_FILE_SIZE) {
      alert('文件过大，上限为 20MB')
      return
    }

    const entryId = `file-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const entry: PendingFile = {
      id: entryId,
      name: file.name,
      size: file.size,
      status: 'parsing',
    }

    setPendingFiles(prev => [...prev, entry])
    setUploading(true)

    try {
      if (isBinaryFile(file.name)) {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch('/api/upload', { method: 'POST', body: formData })
        if (!res.ok) throw new Error('解析失败')
        const data = await res.json()
        if (!data.content) throw new Error('文档内容为空')

        setPendingFiles(prev => prev.map(f =>
          f.id === entryId ? { ...f, content: data.content, status: 'done' as const } : f
        ))
      } else {
        const fileText = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = (ev) => resolve(ev.target?.result as string)
          reader.onerror = () => reject(new Error('读取失败'))
          reader.readAsText(file)
        })

        setPendingFiles(prev => prev.map(f =>
          f.id === entryId ? { ...f, content: fileText, status: 'done' as const } : f
        ))
      }
    } catch (err: any) {
      setPendingFiles(prev => prev.map(f =>
        f.id === entryId ? { ...f, status: 'error' as const, error: err.message || '处理失败' } : f
      ))
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }, [])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await processFile(file)
  }, [processFile])

  const getPlaceholder = () => {
    if (placeholder) return placeholder
    if (isStreaming) return 'AI 正在回复中...'
    if (pendingFiles.length > 0 && pendingFiles.some(f => f.status === 'done')) {
      return '文件已就绪，输入补充说明或直接发送...'
    }
    switch (phase) {
      case 'idle': return '在这里粘贴学习内容，或上传文件开始...'
      case 'design': return '回复 AI 的建议，选择格式或指定重点...'
      case 'done':
      case 'result': return '告诉 AI 修改方向，或说"好的"完成...'
      default: return '输入你的消息...'
    }
  }

  const canSend = (text.trim().length > 0 || pendingFiles.some(f => f.status === 'done')) && !isStreaming

  return (
    <div className="border-t border-border bg-surface/90 backdrop-blur-sm px-5 py-4">
      <div className="mx-auto max-w-4xl">
        {/* ── File cards above input ── */}
        {pendingFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {pendingFiles.map((f) => {
              const info = getFileTypeInfo(f.name)
              const Icon = info.icon
              return (
                <div
                  key={f.id}
                  className={`file-card inline-flex items-center gap-2.5 rounded-xl border px-3.5 py-2.5 ${info.bg} ${info.border}`}
                >
                  {/* Icon */}
                  {f.status === 'parsing' ? (
                    <Loader2 size={16} className="animate-spin text-ink-muted" />
                  ) : f.status === 'error' ? (
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-100">
                      <X size={14} className="text-rose-500" />
                    </div>
                  ) : (
                    <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${info.bg}`}>
                      <Icon size={18} className={info.text} />
                    </div>
                  )}

                  {/* Name + meta */}
                  <div className="min-w-0">
                    <p className={`text-sm font-medium truncate max-w-[200px] ${
                      f.status === 'error' ? 'text-rose-600' : 'text-ink'
                    }`}>
                      {f.name}
                    </p>
                    <p className="text-xs text-ink-muted/50 mt-0.5">
                      {f.status === 'parsing' ? '解析中...' :
                       f.status === 'error' ? (f.error || '处理失败') :
                       `${formatSize(f.size)} · ${info.label}`}
                    </p>
                  </div>

                  {/* Remove */}
                  <button
                    onClick={() => removeFile(f.id)}
                    className="flex-shrink-0 rounded-lg p-1 text-ink-muted/30 hover:text-rose-500 hover:bg-rose-50 transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* ── Input bar ── */}
        <div className="flex items-end gap-2.5 rounded-2xl border border-border bg-paper px-4 py-2.5 focus-within:border-primary-300 focus-within:ring-2 focus-within:ring-primary-100/60 transition-all">
          {/* Upload button */}
          <button
            onClick={() => fileRef.current?.click()}
            disabled={isStreaming || uploading}
            className="flex-shrink-0 rounded-xl p-2 text-ink-muted/40 hover:text-ink-soft hover:bg-paper-dark transition-colors disabled:opacity-30"
            title="上传文件"
          >
            {uploading ? <Loader2 size={17} className="animate-spin" /> : <Paperclip size={17} />}
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
            className="flex-1 resize-none bg-transparent text-base text-ink placeholder:text-ink-muted/35 outline-none disabled:opacity-50 max-h-52 leading-relaxed py-0.5"
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={`flex-shrink-0 rounded-xl p-2 transition-all ${
              canSend
                ? 'bg-primary-500 text-white hover:bg-primary-600 shadow-sm'
                : 'text-ink-muted/15 cursor-not-allowed'
            }`}
          >
            <Send size={16} />
          </button>
        </div>

        <p className="mt-2.5 text-center text-xs text-ink-muted/35">
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
