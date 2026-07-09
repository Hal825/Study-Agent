import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, ClipboardPaste, FileText, X, File, FileType } from 'lucide-react'

interface UploadZoneProps {
  value: string
  onChange: (content: string) => void
}

interface AttachedFile {
  name: string
  size: number
  type: string
  isClipboard: boolean
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadZone({ value, onChange }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Auto-detect clipboard
  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const text = await navigator.clipboard.readText()
        if (!cancelled && text.trim().length > 0 && !value) {
          onChange(text)
          setAttachedFile({ name: '剪贴板内容', size: new Blob([text]).size, type: 'text/plain', isClipboard: true })
        }
      } catch { /* no permission / no content */ }
    }
    check()
    return () => { cancelled = true }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragging(true) }, [])
  const handleDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragging(false) }, [])
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false)
    const file = e.dataTransfer.files[0]; if (file) read(file)
  }, [])
  const handleSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (file) read(file)
  }, [])

  const read = (file: File) => {
    setAttachedFile({ name: file.name, size: file.size, type: file.type || 'text/plain', isClipboard: false })
    const r = new FileReader()
    r.onload = (e) => onChange(e.target?.result as string)
    r.readAsText(file)
  }

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text.trim()) {
        onChange(text)
        setAttachedFile({ name: '剪贴板内容', size: new Blob([text]).size, type: 'text/plain', isClipboard: true })
      }
    } catch { /* ignore */ }
  }, [onChange])

  const handleClear = () => { onChange(''); setAttachedFile(null) }

  const fn = attachedFile?.name ?? ''
  const isMd = fn.endsWith('.md') || fn.endsWith('.markdown')
  const isTxt = fn.endsWith('.txt')

  // --- File attached state ---
  if (value && attachedFile) {
    return (
      <div className="animate-fade-in">
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-card">
          <div className="flex items-start gap-4">
            <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl ${
              attachedFile.isClipboard
                ? 'bg-gold-50 text-gold-600'
                : isMd ? 'bg-primary-50 text-primary-600'
                : isTxt ? 'bg-emerald-50 text-emerald-600'
                : 'bg-paper-dark text-ink-muted'
            }`}>
              {attachedFile.isClipboard ? <ClipboardPaste size={22} />
                : isMd ? <FileType size={22} />
                : isTxt ? <FileText size={22} />
                : <File size={22} />}
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-semibold text-ink truncate">{attachedFile.name}</h4>
              <p className="mt-0.5 text-xs text-ink-muted">
                {attachedFile.isClipboard ? <>剪贴板 · {value.length} 字</> : <>{formatSize(attachedFile.size)} · {attachedFile.type || '未知类型'}</>}
              </p>
              {attachedFile.isClipboard && (
                <p className="mt-1.5 text-xs text-ink-muted/70 line-clamp-2">{value.slice(0, 100)}{value.length > 100 ? '...' : ''}</p>
              )}
            </div>
            <button onClick={handleClear} className="rounded-lg p-2 text-ink-muted/40 hover:bg-paper hover:text-ink-soft transition-colors" title="移除">
              <X size={15} />
            </button>
          </div>
        </div>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border py-2.5 text-xs text-ink-muted/50 hover:border-ink-muted/30 hover:text-ink-muted transition-colors"
        >
          <Upload size={12} /> 添加更多文件
        </button>
      </div>
    )
  }

  // --- Empty state ---
  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-200 ${
        isDragging
          ? 'border-ink/30 bg-ink/[0.02] scale-[1.01]'
          : 'border-border bg-surface hover:border-ink/15 hover:bg-paper/50'
      }`}
    >
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-paper-dark">
        <Upload size={22} className="text-ink-muted" />
      </div>
      <h3 className="mb-1.5 text-base font-semibold text-ink">上传学习内容</h3>
      <p className="mb-6 text-sm text-ink-muted">拖拽文件到此处，或使用下方按钮</p>
      <div className="flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-xl bg-ink px-5 py-2.5 text-sm font-medium text-white hover:bg-ink/85 transition-colors shadow-sm"
        >
          <Upload size={14} /> 选择文件
        </button>
        <span className="text-sm text-ink-muted/50">或</span>
        <button
          type="button"
          onClick={handlePaste}
          className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-5 py-2.5 text-sm font-medium text-ink-soft hover:bg-paper transition-colors"
        >
          <ClipboardPaste size={14} /> 从剪贴板粘贴
        </button>
      </div>
      <p className="mt-4 text-xs text-ink-muted/50">支持 .md .txt .json .csv .html .log 等文本文件</p>
      <input ref={fileInputRef} type="file" accept=".md,.txt,.markdown,.json,.csv,.html,.xml,.yaml,.yml,.log" onChange={handleSelect} className="hidden" />
    </div>
  )
}
