import { useCallback, useRef, useState } from 'react'
import { Upload, ClipboardPaste, FileText, X } from 'lucide-react'

interface UploadZoneProps {
  value: string
  onChange: (content: string) => void
}

export default function UploadZone({ value, onChange }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (file) {
      readFile(file)
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      readFile(file)
    }
  }, [])

  const readFile = (file: File) => {
    if (!file.name.endsWith('.md') && !file.name.endsWith('.txt')) {
      alert('目前仅支持 .md 和 .txt 文件')
      return
    }
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      onChange(text)
    }
    reader.readAsText(file)
  }

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text.trim()) {
        onChange(text)
        setFileName('剪贴板内容')
      }
    } catch {
      alert('无法读取剪贴板，请检查权限设置')
    }
  }, [onChange])

  const handleClear = () => {
    onChange('')
    setFileName(null)
  }

  if (value) {
    return (
      <div className="animate-fade-in space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <FileText size={16} />
            <span>{fileName ?? '已输入内容'}</span>
            <span className="text-gray-400">({value.length} 字)</span>
          </div>
          <button
            onClick={handleClear}
            className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-100 hover:text-red-500 transition-colors"
          >
            <X size={14} />
            清除
          </button>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 max-h-60 overflow-y-auto">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
            {value.slice(0, 2000)}
            {value.length > 2000 && (
              <span className="text-gray-400">\n\n... (内容已截断，共 {value.length} 字)</span>
            )}
          </pre>
        </div>
      </div>
    )
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-200 ${
        isDragging
          ? 'border-primary-400 bg-primary-50/50 scale-[1.01]'
          : 'border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50/50'
      }`}
    >
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-50">
        <Upload size={24} className="text-primary-500" />
      </div>
      <h3 className="mb-2 text-lg font-semibold text-gray-900">上传学习内容</h3>
      <p className="mb-6 text-sm text-gray-500">
        拖拽文件到此处，或使用下方的输入方式
      </p>
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-700 transition-colors shadow-sm"
        >
          <Upload size={16} />
          选择文件
        </button>
        <span className="text-sm text-gray-400">或</span>
        <button
          onClick={handlePaste}
          className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          <ClipboardPaste size={16} />
          粘贴内容
        </button>
      </div>
      <p className="mt-4 text-xs text-gray-400">支持 .md、.txt 文件</p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.txt"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  )
}
