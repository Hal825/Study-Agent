import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, ClipboardPaste, FileText, X } from 'lucide-react'

interface UploadZoneProps {
  value: string
  onChange: (content: string) => void
}

const SUPPORTED = '.md, .txt, .json, .csv, .html, .yaml, .xml, .log'

export default function UploadZone({ value, onChange }: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false)
  const [fileName, setFileName] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!value) {
      navigator.clipboard.readText().then((text) => {
        if (text.trim().length > 20) {
          onChange(text)
          setFileName('剪贴板内容')
        }
      }).catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFile = useCallback((file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      if (text) { onChange(text); setFileName(file.name) }
    }
    reader.readAsText(file)
  }, [onChange])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handlePaste = useCallback(() => {
    navigator.clipboard.readText().then((text) => {
      if (text.trim()) { onChange(text); setFileName('剪贴板内容') }
    }).catch(() => {})
  }, [onChange])

  const handleClear = () => { onChange(''); setFileName('') }

  // File attached
  if (value && fileName) {
    return (
      <div className="animate-fade-in rounded-3xl border border-border bg-surface p-5">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-primary-50 text-primary-500">
            <FileText size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-ink truncate">{fileName}</p>
            <p className="text-2xs text-ink-muted mt-1 line-clamp-2">
              {value.slice(0, 200)}{value.length > 200 ? '...' : ''}
            </p>
          </div>
          <button
            onClick={handleClear}
            className="rounded-lg p-1.5 text-ink-muted/30 hover:bg-paper-dark hover:text-ink-soft transition-colors"
          >
            <X size={15} />
          </button>
        </div>
      </div>
    )
  }

  // Empty dropzone
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`rounded-3xl border-2 border-dashed p-10 text-center transition-all duration-200 ${
        dragOver
          ? 'border-primary-300 bg-primary-50/40 scale-[1.01]'
          : 'border-border hover:border-primary-200 hover:bg-paper/60'
      }`}
    >
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-paper-dark text-ink-muted/30">
        <Upload size={22} />
      </div>
      <h3 className="text-sm font-semibold text-ink-soft mb-1">上传学习内容</h3>
      <p className="text-xs text-ink-muted mb-5">拖拽文件到此处，或使用下方按钮</p>

      <div className="flex items-center justify-center gap-3">
        <button
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-xl bg-primary-50 px-4 py-2 text-xs font-medium text-primary-600 hover:bg-primary-100 transition-colors"
        >
          <Upload size={13} /> 选择文件
        </button>
        <button
          onClick={handlePaste}
          className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-xs font-medium text-ink-soft hover:bg-paper-dark transition-colors"
        >
          <ClipboardPaste size={13} /> 从剪贴板粘贴
        </button>
      </div>

      <p className="mt-4 text-2xs text-ink-muted/40">支持 {SUPPORTED} 格式</p>

      <input ref={fileRef} type="file" accept=".md,.txt,.markdown,.json,.csv,.html,.xml,.yaml,.yml,.log" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }} className="hidden" />
    </div>
  )
}
