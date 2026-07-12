import { useState, useCallback, useRef } from 'react'
import { Copy, Download, ChevronDown, RotateCcw } from 'lucide-react'
import { useOutputStore } from '../../stores/outputStore'
import { NOTE_TEMPLATES } from '../../types'
import { useSSE } from '../../hooks/useSSE'
import {
  markdownToPlainText,
  downloadAsPDF,
  downloadAsDocx,
} from '../../services/agent'
import UploadZone from '../../components/common/UploadZone'
import AgentProgress from '../../components/workflow/AgentProgress'
import MarkdownRenderer from '../../components/common/MarkdownRenderer'

export default function NoteTool() {
  const [content, setContent] = useState('')
  const [usedTemplate, setUsedTemplate] = useState<string | null>(null)
  const [downloadOpen, setDownloadOpen] = useState(false)

  const addOutput = useOutputStore((s) => s.addOutput)
  const {
    isConnected, currentStage, stageIndex, result, isDone, error,
    confirmRequired, confirmQuestion, confirmOptions,
    connect, confirmAndResume: sseConfirmAndResume, rejectConfirm, reset,
  } = useSSE()

  const canGenerate = content.trim().length > 0

  const handleGenerate = useCallback(() => {
    if (!canGenerate) return
    // 使用默认模板启动；用户在 Human-in-the-Loop 确认环节再选定最终模板
    connect('/api/agent/note/stream', {
      content,
      template: 'outline',
    })
  }, [canGenerate, content, connect])

  // 包装 confirmAndResume，记录用户最终选定的模板
  const handleConfirm = useCallback((templateId: string) => {
    setUsedTemplate(templateId)
    sseConfirmAndResume(templateId)
  }, [sseConfirmAndResume])

  // Save to output history when done (only once per result)
  const savedRef = useRef(false)
  if (isDone && result && !savedRef.current) {
    savedRef.current = true
    const tplId = usedTemplate ?? 'outline'
    const tpl = NOTE_TEMPLATES.find((t) => t.id === tplId)
    if (tpl) addOutput(tpl.id, result)
  }
  if (!isDone) savedRef.current = false

  const handleReset = () => {
    reset()
    setContent('')
    setUsedTemplate(null)
  }

  const handleCopy = async () => {
    if (result) await navigator.clipboard.writeText(result)
  }

  const handleDownloadMD = () => {
    if (!result) return
    const blob = new Blob([result], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'notes.md'; a.click()
    URL.revokeObjectURL(url)
    setDownloadOpen(false)
  }

  const handleDownloadTXT = () => {
    if (!result) return
    const text = markdownToPlainText(result)
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'notes.txt'; a.click()
    URL.revokeObjectURL(url)
    setDownloadOpen(false)
  }

  const handleDownloadPDF = async () => {
    if (!result) return
    try { await downloadAsPDF(result, 'notes') }
    catch { alert('PDF 导出失败，请确保后端服务已启动') }
    setDownloadOpen(false)
  }

  const handleDownloadDocx = async () => {
    if (!result) return
    try { await downloadAsDocx(result, 'notes') }
    catch { alert('Word 导出失败，请确保后端服务已启动') }
    setDownloadOpen(false)
  }

  // Confirmation dialog — shown when agent pauses for human input
  if (confirmRequired) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 animate-fade-in">
        <AgentProgress
          currentStage="等待确认模板..."
          stageIndex={3}
          isConnected={false}
        />

        <div className="mt-8 rounded-2xl border border-primary-100 bg-primary-50/30 p-8 text-center">
          <div className="mb-2 text-3xl">🤔</div>
          <h3 className="mb-1 font-display text-lg font-semibold text-ink">
            确认模板选择
          </h3>
          <p className="mb-6 text-sm text-ink-muted">
            {confirmQuestion || '请选择笔记模板以继续生成'}
          </p>

          <div className="mb-6 flex flex-wrap justify-center gap-3">
            {(confirmOptions.length > 0 ? confirmOptions : ['outline', 'summary', 'cornell', 'qa'])
              .map((opt) => {
                const tpl = NOTE_TEMPLATES.find((t) => t.id === opt)
                const emoji: Record<string, string> = {
                  outline: '🌳', summary: '📄', cornell: '📋', qa: '💬',
                }
                return (
                  <button
                    key={opt}
                    onClick={() => handleConfirm(opt)}
                    className="rounded-xl border border-primary-200 bg-white px-5 py-3 text-sm font-medium text-primary-700
                               hover:bg-primary-50 hover:border-primary-300 transition-colors shadow-sm"
                  >
                    {emoji[opt] ?? '📝'} {tpl?.name ?? opt}
                  </button>
                )
              })}
          </div>

          <button
            onClick={rejectConfirm}
            className="text-xs text-ink-muted hover:text-ink-soft underline"
          >
            取消生成
          </button>
        </div>
      </div>
    )
  }

  // If processing, show agent progress
  if (isConnected || currentStage) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 animate-fade-in">
        <AgentProgress currentStage={currentStage} stageIndex={stageIndex} isConnected={isConnected} />
        {error && (
          <div className="mt-8 rounded-2xl border border-red-100 bg-red-50 p-5 text-center">
            <p className="text-sm text-red-600">{error}</p>
            <button
              onClick={handleReset}
              className="mt-3 inline-flex items-center gap-2 rounded-xl border border-red-200 px-4 py-2 text-xs font-medium text-red-600 hover:bg-red-100 transition-colors"
            >
              <RotateCcw size={13} /> 重新开始
            </button>
          </div>
        )}
      </div>
    )
  }

  // Result view
  if (isDone && result) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 animate-fade-in">
        {/* Toolbar */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="font-display text-xl font-bold text-ink tracking-tight">生成的笔记</h2>
            <p className="mt-1 text-xs text-ink-muted">
              {NOTE_TEMPLATES.find((t) => t.id === usedTemplate)?.name ?? ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 rounded-xl border border-border px-3.5 py-2 text-sm text-ink-soft hover:bg-paper-dark transition-colors"
            >
              <Copy size={14} /> 复制
            </button>
            <div className="relative">
              <button
                onClick={() => setDownloadOpen(!downloadOpen)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-primary-500 px-3.5 py-2 text-sm text-white hover:bg-primary-600 transition-colors"
              >
                <Download size={14} /> 下载 <ChevronDown size={12} />
              </button>
              {downloadOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setDownloadOpen(false)} />
                  <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-2xl border border-border bg-surface py-1 shadow-panel animate-fade-in">
                    {[
                      { label: 'Markdown (.md)', action: handleDownloadMD },
                      { label: '纯文本 (.txt)', action: handleDownloadTXT },
                      { label: 'PDF', action: handleDownloadPDF },
                      { label: 'Word (.docx)', action: handleDownloadDocx },
                    ].map((opt) => (
                      <button
                        key={opt.label}
                        onClick={opt.action}
                        className="w-full px-4 py-2 text-left text-xs text-ink-soft hover:bg-paper-dark transition-colors"
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 rounded-xl border border-border px-3.5 py-2 text-sm text-ink-soft hover:bg-paper-dark transition-colors"
            >
              <RotateCcw size={14} /> 重新生成
            </button>
          </div>
        </div>

        {/* Rendered markdown */}
        <div className="rounded-3xl border border-border bg-surface p-8 shadow-card">
          <MarkdownRenderer content={result} />
        </div>
      </div>
    )
  }

  // Input view — upload content, template will be chosen during Agent confirmation
  return (
    <div className="mx-auto max-w-3xl px-6 py-12 animate-fade-in">
      {/* Header */}
      <div className="mb-8 text-center">
        <h2 className="font-display text-2xl font-bold text-ink tracking-tight">笔记生成</h2>
        <p className="mt-1.5 text-sm text-ink-muted">
          AI Agent 将自动解析内容、提取知识点，中途会让你选择模板
        </p>
      </div>

      {/* Upload zone */}
      <div className="mb-8">
        <UploadZone value={content} onChange={setContent} />
      </div>

      {/* Generate button */}
      <div className="text-center">
        <button
          onClick={handleGenerate}
          disabled={!canGenerate}
          className={`inline-flex items-center gap-2 rounded-2xl px-8 py-3 text-sm font-semibold transition-all ${
            canGenerate
              ? 'bg-primary-500 text-white hover:bg-primary-600 shadow-sm hover:shadow-md'
              : 'cursor-not-allowed bg-paper-dark text-ink-muted/30'
          }`}
        >
          开始生成笔记
        </button>
        <p className="mt-3 text-2xs text-ink-muted/40">
          {!content.trim() ? '请先上传学习内容' : 'AI Agent 将自动分析并在确认模板后生成笔记'}
        </p>
      </div>
    </div>
  )
}
