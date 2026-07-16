import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Upload, ClipboardPaste, FileText, Image, X, Loader2, AlertTriangle } from 'lucide-react'

// ---------------------------------------------------------------
// Types
// ---------------------------------------------------------------

interface UploadZoneProps {
  value: string
  onChange: (content: string) => void
}

interface FileEntry {
  id: string
  name: string
  size: number   // bytes
  content: string
  status: 'parsing' | 'done' | 'error'
  error?: string
}

// ---------------------------------------------------------------
// Constants
// ---------------------------------------------------------------

const SUPPORTED = '.md, .txt, .json, .csv, .html, .yaml, .xml, .log, .docx, .pdf, .jpg, .png, .webp'
const BINARY_EXTENSIONS = ['.docx', '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
const DEFAULT_MAX_TOTAL_MB = 50

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------

function isBinaryFile(filename: string): boolean {
  const ext = '.' + filename.split('.').pop()?.toLowerCase()
  return BINARY_EXTENSIONS.includes(ext)
}

function isImageFile(filename: string): boolean {
  const ext = '.' + filename.split('.').pop()?.toLowerCase()
  return IMAGE_EXTENSIONS.includes(ext)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileIcon(filename: string) {
  return isImageFile(filename) ? Image : FileText
}

// ---------------------------------------------------------------
// Component
// ---------------------------------------------------------------

export default function UploadZone({ value, onChange }: UploadZoneProps) {
  const [files, setFiles] = useState<FileEntry[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [parseError, setParseError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const errorTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const nextId = useId()

  const totalSize = files.reduce((sum, f) => sum + f.size, 0)
  const maxTotalBytes = DEFAULT_MAX_TOTAL_MB * 1024 * 1024
  const sizeRatio = totalSize / maxTotalBytes

  // Sync value to parent
  const syncValue = useCallback((entries: FileEntry[]) => {
    const done = entries.filter(f => f.status === 'done' && f.content.trim())
    if (done.length === 0) {
      onChange('')
    } else if (done.length === 1) {
      onChange(done[0].content)
    } else {
      // Concatenate with file-name headers
      const merged = done
        .map(f => `## ${f.name}\n\n${f.content}`)
        .join('\n\n---\n\n')
      onChange(merged)
    }
  }, [onChange])

  // Auto clipboard read on mount
  useEffect(() => {
    if (!value) {
      navigator.clipboard.readText().then((text) => {
        if (text.trim().length > 20) {
          setFiles([{
            id: `clipboard-${Date.now()}`,
            name: '剪贴板内容',
            size: new Blob([text]).size,
            content: text,
            status: 'done',
          }])
          onChange(text)
        }
      }).catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Cleanup error timer
  useEffect(() => {
    return () => { if (errorTimerRef.current) clearTimeout(errorTimerRef.current) }
  }, [])

  const showError = useCallback((msg: string) => {
    setParseError(msg)
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current)
    errorTimerRef.current = setTimeout(() => setParseError(''), 5000)
  }, [])

  // ---------------------------------------------------------------
  // Process a single file (text locally, binary via API)
  // ---------------------------------------------------------------

  const processFile = useCallback(async (file: File, entryId: string) => {
    if (isBinaryFile(file.name)) {
      // Binary → upload to backend
      try {
        const formData = new FormData()
        formData.append('file', file)

        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        })

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.detail || `服务器解析失败 (${res.status})`)
        }

        const data = await res.json()
        if (!data.content) throw new Error('文档内容为空')

        setFiles(prev => {
          const next = prev.map(f =>
            f.id === entryId ? { ...f, content: data.content, status: 'done' as const } : f
          )
          syncValue(next)
          return next
        })
      } catch (err: any) {
        const msg = err instanceof Error ? err.message : '解析失败'
        setFiles(prev => prev.map(f =>
          f.id === entryId ? { ...f, status: 'error' as const, error: msg } : f
        ))
      }
    } else {
      // Text → read locally
      return new Promise<void>((resolve) => {
        const reader = new FileReader()
        reader.onload = (e) => {
          const text = e.target?.result as string
          if (text) {
            setFiles(prev => {
              const next = prev.map(f =>
                f.id === entryId ? { ...f, content: text, status: 'done' as const } : f
              )
              syncValue(next)
              return next
            })
          } else {
            setFiles(prev => prev.map(f =>
              f.id === entryId ? { ...f, status: 'error' as const, error: '文件读取失败' } : f
            ))
          }
          resolve()
        }
        reader.onerror = () => {
          setFiles(prev => prev.map(f =>
            f.id === entryId ? { ...f, status: 'error' as const, error: '文件读取失败' } : f
          ))
          resolve()
        }
        reader.readAsText(file)
      })
    }
  }, [syncValue])

  // ---------------------------------------------------------------
  // Add files (with size check)
  // ---------------------------------------------------------------

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    setParseError('')
    const incoming = Array.from(newFiles)
    if (incoming.length === 0) return

    // Check total size
    const currentTotal = files.reduce((s, f) => s + f.size, 0)
    const incomingTotal = incoming.reduce((s, f) => s + f.size, 0)
    const newTotal = currentTotal + incomingTotal

    if (newTotal > maxTotalBytes) {
      showError(
        `文件总大小 (${formatSize(newTotal)}) 超过限制 (${DEFAULT_MAX_TOTAL_MB} MB)，` +
        `当前已用 ${formatSize(currentTotal)}，无法添加 ${incoming.length} 个文件`
      )
      // Add as many as fit
      let remaining = maxTotalBytes - currentTotal
      const accepted: File[] = []
      for (const f of incoming) {
        if (f.size <= remaining) {
          accepted.push(f)
          remaining -= f.size
        }
      }
      if (accepted.length === 0) return
      incoming.length = 0
      incoming.push(...accepted)
    }

    // Create entries and start processing
    const entries: FileEntry[] = incoming.map((f, i) => ({
      id: `${nextId}-${Date.now()}-${i}`,
      name: f.name,
      size: f.size,
      content: '',
      status: 'parsing' as const,
    }))

    setFiles(prev => [...prev, ...entries])

    // Process each file (don't await — let them run concurrently)
    entries.forEach((entry, i) => {
      processFile(incoming[i], entry.id)
    })
  }, [files, maxTotalBytes, nextId, showError, processFile])

  // ---------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files)
  }, [addFiles])

  const handlePaste = useCallback(() => {
    navigator.clipboard.readText().then((text) => {
      if (!text.trim()) return
      const entry: FileEntry = {
        id: `paste-${Date.now()}`,
        name: '剪贴板内容',
        size: new Blob([text]).size,
        content: text,
        status: 'done',
      }
      setFiles(prev => {
        const next = [...prev, entry]
        syncValue(next)
        return next
      })
    }).catch(() => {})
  }, [syncValue])

  const handleRemove = useCallback((id: string) => {
    setFiles(prev => {
      const next = prev.filter(f => f.id !== id)
      syncValue(next)
      return next
    })
  }, [syncValue])

  const handleClearAll = useCallback(() => {
    setFiles([])
    onChange('')
    setParseError('')
  }, [onChange])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files)
    }
    // Reset so re-selecting the same file works
    if (fileRef.current) fileRef.current.value = ''
  }, [addFiles])

  // ---------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------

  const doneCount = files.filter(f => f.status === 'done').length
  const parsingCount = files.filter(f => f.status === 'parsing').length
  const errorCount = files.filter(f => f.status === 'error').length

  return (
    <div className="space-y-4">
      {/* ---- Global error banner ---- */}
      {parseError && (
        <div className="animate-fade-in rounded-2xl border border-red-200 bg-red-50/50 px-4 py-3 flex items-center gap-3">
          <AlertTriangle size={16} className="text-red-500 flex-shrink-0" />
          <p className="text-xs text-red-600 flex-1">{parseError}</p>
          <button
            onClick={() => setParseError('')}
            className="text-red-400 hover:text-red-600"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* ---- File list ---- */}
      {files.length > 0 && (
        <div className="rounded-2xl border border-border bg-surface overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-border/60 bg-paper/50">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-ink-muted/50" />
              <span className="text-xs font-medium text-ink-soft">
                {doneCount}/{files.length} 个文件
                {parsingCount > 0 && (
                  <span className="text-primary-500 ml-1">({parsingCount} 解析中)</span>
                )}
                {errorCount > 0 && (
                  <span className="text-red-500 ml-1">({errorCount} 失败)</span>
                )}
              </span>
            </div>
            <div className="flex items-center gap-3">
              {/* Size bar */}
              <div className="hidden sm:flex items-center gap-2">
                <div className="h-1.5 w-20 rounded-full bg-paper-dark overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      sizeRatio > 0.9 ? 'bg-red-400' : sizeRatio > 0.7 ? 'bg-amber-400' : 'bg-primary-400'
                    }`}
                    style={{ width: `${Math.min(sizeRatio * 100, 100)}%` }}
                  />
                </div>
                <span className={`text-xs tabular-nums ${
                  sizeRatio > 0.9 ? 'text-red-500 font-medium' : 'text-ink-muted/50'
                }`}>
                  {formatSize(totalSize)} / {DEFAULT_MAX_TOTAL_MB} MB
                </span>
              </div>
              <button
                onClick={handleClearAll}
                className="text-xs text-ink-muted/30 hover:text-red-500 transition-colors"
              >
                全部清除
              </button>
            </div>
          </div>

          {/* File rows */}
          <ul className="divide-y divide-border/40">
            {files.map((f) => {
              const Icon = fileIcon(f.name)
              return (
                <li key={f.id} className="flex items-center gap-3 px-5 py-2.5 hover:bg-paper/40 transition-colors">
                  {/* Icon */}
                  <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg ${
                    f.status === 'error' ? 'bg-red-50 text-red-400' :
                    f.status === 'parsing' ? 'bg-primary-50 text-primary-400' :
                    'bg-paper-dark text-ink-muted/40'
                  }`}>
                    {f.status === 'parsing'
                      ? <Loader2 size={14} className="animate-spin" />
                      : <Icon size={14} />
                    }
                  </div>

                  {/* Name + meta */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs truncate ${
                      f.status === 'error' ? 'text-red-600' : 'text-ink'
                    }`}>
                      {f.name}
                    </p>
                    <p className="text-xs text-ink-muted/40">
                      {formatSize(f.size)}
                      {f.status === 'error' && f.error && (
                        <span className="text-red-400 ml-2">{f.error}</span>
                      )}
                    </p>
                  </div>

                  {/* Remove button */}
                  <button
                    onClick={() => handleRemove(f.id)}
                    className="rounded-lg p-1.5 text-ink-muted/20 hover:text-red-500 hover:bg-red-50 transition-colors flex-shrink-0"
                    aria-label={`移除 ${f.name}`}
                  >
                    <X size={13} />
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* ---- Drop zone (always visible) ---- */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`rounded-3xl border-2 border-dashed p-8 text-center transition-all duration-200 ${
          dragOver
            ? 'border-primary-300 bg-primary-50/40 scale-[1.01]'
            : 'border-border hover:border-primary-200 hover:bg-paper/60'
        }`}
      >
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-2xl bg-paper-dark text-ink-muted/30">
          <Upload size={20} />
        </div>
        <h3 className="text-sm font-semibold text-ink-soft mb-1">
          {files.length > 0 ? '继续添加文件' : '上传学习内容'}
        </h3>
        <p className="text-xs text-ink-muted mb-4">拖拽文件到此处，或使用下方按钮</p>

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

        <p className="mt-3 text-xs text-ink-muted/40">
          支持 {SUPPORTED} 格式 &middot; 总上限 {DEFAULT_MAX_TOTAL_MB} MB
        </p>

        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".md,.txt,.markdown,.json,.csv,.html,.xml,.yaml,.yml,.log,.docx,.pdf,.jpg,.jpeg,.png,.webp,.gif,.bmp"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>
    </div>
  )
}
