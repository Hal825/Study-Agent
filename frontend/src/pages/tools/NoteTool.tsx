import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, RotateCcw, Copy, Download, ChevronDown } from 'lucide-react'
import { useWorkflowStore } from '../../stores/workflowStore'
import { useAgentStore } from '../../stores/agentStore'
import { useOutputStore } from '../../stores/outputStore'
import { NOTE_TEMPLATES, type WorkflowStep, type NoteTemplate } from '../../types'
import {
  agentGenerateNote,
  markdownToPlainText,
  downloadAsPDF,
  downloadAsDocx,
} from '../../services/agent'
import WorkflowContainer from '../../components/workflow/WorkflowContainer'
import UploadZone from '../../components/common/UploadZone'
import AgentProgress from '../../components/workflow/AgentProgress'
import MarkdownRenderer from '../../components/common/MarkdownRenderer'

export default function NoteTool() {
  const {
    step,
    content,
    selectedTemplate,
    result,
    setStep,
    setContent,
    setSelectedTemplate,
    setResult,
    reset,
  } = useWorkflowStore()

  const { startProcessing, advanceStage, finishProcessing, setError } = useAgentStore()
  const addOutput = useOutputStore((s) => s.addOutput)

  // 保存到输出历史（结果步骤进入时）
  const savedRef = useRef(false)
  useEffect(() => {
    if (step === 'result' && result && selectedTemplate && !savedRef.current) {
      addOutput(selectedTemplate, result)
      savedRef.current = true
    }
    if (step !== 'result') {
      savedRef.current = false
    }
  }, [step, result, selectedTemplate, addOutput])

  // ==========================================
  // Step transitions
  // ==========================================
  const canProceed = (): boolean => {
    switch (step) {
      case 'input': return content.trim().length > 0
      case 'config': return selectedTemplate !== null
      default: return true
    }
  }

  const nextStep = useCallback(async () => {
    if (step === 'config' && selectedTemplate) {
      // Start agent processing
      const template = NOTE_TEMPLATES.find((t) => t.id === selectedTemplate)!
      setStep('process')
      startProcessing()

      try {
        const finalResult = await agentGenerateNote(template, content, advanceStage)
        setResult(finalResult)
        finishProcessing()
        setStep('result')
      } catch {
        setError('处理过程中出现错误，请重试')
      }
    } else {
      const steps: WorkflowStep[] = ['input', 'config', 'process', 'result']
      const idx = steps.indexOf(step)
      if (idx < steps.length - 1) {
        setStep(steps[idx + 1])
      }
    }
  }, [step, selectedTemplate, content, startProcessing, advanceStage, finishProcessing, setError, setResult, setStep])

  const prevStep = () => {
    const steps: WorkflowStep[] = ['input', 'config', 'process', 'result']
    const idx = steps.indexOf(step)
    if (idx > 0) {
      setStep(steps[idx - 1])
    }
  }

  const handleReset = () => {
    reset()
  }

  // ==========================================
  // Export actions
  // ==========================================
  const [downloadOpen, setDownloadOpen] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result)
  }

  const handleDownloadMD = () => {
    const blob = new Blob([result], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'notes.md'
    a.click()
    URL.revokeObjectURL(url)
    setDownloadOpen(false)
  }

  const handleDownloadTXT = () => {
    const text = markdownToPlainText(result)
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'notes.txt'
    a.click()
    URL.revokeObjectURL(url)
    setDownloadOpen(false)
  }

  const handleDownloadPDF = async () => {
    try {
      await downloadAsPDF(result, 'notes')
    } catch {
      alert('PDF 导出失败，请确保后端服务已启动')
    }
    setDownloadOpen(false)
  }

  const handleDownloadDocx = async () => {
    try {
      await downloadAsDocx(result, 'notes')
    } catch {
      alert('Word 导出失败，请确保后端服务已启动')
    }
    setDownloadOpen(false)
  }

  // ==========================================
  // Step renderers
  // ==========================================
  const renderInputStep = () => (
    <UploadZone value={content} onChange={setContent} />
  )

  const renderConfigStep = () => (
    <div className="animate-fade-in">
      <h3 className="mb-5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
        选择笔记模板
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {NOTE_TEMPLATES.map((tpl) => {
          const isSelected = selectedTemplate === tpl.id
          return (
            <NoteTemplateCard
              key={tpl.id}
              template={tpl}
              isSelected={isSelected}
              onSelect={() => setSelectedTemplate(tpl.id)}
            />
          )
        })}
      </div>
    </div>
  )

  const renderProcessStep = () => <AgentProgress />

  const renderResultStep = () => (
    <div className="animate-fade-in">
      {/* Toolbar */}
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
          生成的笔记
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-ink-soft hover:bg-paper transition-colors"
          >
            <Copy size={14} />
            复制
          </button>
          <div className="relative">
            <button
              onClick={() => setDownloadOpen(!downloadOpen)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-sm text-white hover:bg-ink/85 transition-colors"
            >
              <Download size={14} />
              下载
              <ChevronDown size={12} />
            </button>
            {downloadOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setDownloadOpen(false)} />
                <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-xl border border-border bg-surface py-1 shadow-panel animate-fade-in">
                  {[
                    { label: 'Markdown (.md)', action: handleDownloadMD },
                    { label: '纯文本 (.txt)', action: handleDownloadTXT },
                    { label: 'PDF', action: handleDownloadPDF },
                    { label: 'Word (.docx)', action: handleDownloadDocx },
                  ].map((opt) => (
                    <button
                      key={opt.label}
                      onClick={opt.action}
                      className="w-full px-4 py-2 text-left text-sm text-ink-soft hover:bg-paper transition-colors"
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Rendered markdown */}
      <div className="rounded-2xl border border-border bg-surface p-6 sm:p-8 shadow-card">
        <MarkdownRenderer content={result} />
      </div>
    </div>
  )

  // ==========================================
  // Step content map
  // ==========================================
  const stepContent: Record<WorkflowStep, React.ReactNode> = {
    input: renderInputStep(),
    config: renderConfigStep(),
    process: renderProcessStep(),
    result: renderResultStep(),
  }

  return (
    <WorkflowContainer
      currentStep={step}
      title="笔记生成"
      description="上传学习内容，选择笔记模板，AI 将自动为您生成结构化笔记"
    >
      {/* Step content */}
      {stepContent[step]}

      {/* Navigation buttons */}
      <div className="mt-10 flex items-center justify-between border-t border-border pt-6">
        <div>
          {step !== 'input' && step !== 'process' && (
            <button
              onClick={prevStep}
              className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-ink-soft hover:bg-paper transition-colors"
            >
              <ArrowLeft size={16} />
              上一步
            </button>
          )}
        </div>
        <div className="flex items-center gap-3">
          {step === 'result' ? (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-ink-soft hover:bg-paper transition-colors"
            >
              <RotateCcw size={16} />
              重新生成
            </button>
          ) : step !== 'process' ? (
            <button
              onClick={nextStep}
              disabled={!canProceed()}
              className={`inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium transition-all ${
                canProceed()
                  ? 'bg-ink text-white hover:bg-ink/85 shadow-sm'
                  : 'cursor-not-allowed bg-paper-dark text-ink-muted/40'
              }`}
            >
              {step === 'config' ? '开始生成' : '下一步'}
              <ArrowRight size={16} />
            </button>
          ) : null}
        </div>
      </div>
    </WorkflowContainer>
  )
}

// ============================================================
// Note template selection card
// ============================================================
function NoteTemplateCard({
  template,
  isSelected,
  onSelect,
}: {
  template: NoteTemplate
  isSelected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`rounded-2xl border p-5 text-left transition-all duration-200 ${
        isSelected
          ? 'border-ink/30 bg-paper shadow-sm'
          : 'border-border bg-surface hover:border-ink/15 hover:bg-paper/50'
      }`}
    >
      <div className="mb-2 text-2xl">{template.icon === 'list-tree' ? '🌳' : template.icon === 'file-text' ? '📄' : template.icon === 'layout-panel-top' ? '📋' : '💬'}</div>
      <h4
        className={`mb-1 text-sm font-semibold ${
          isSelected ? 'text-ink' : 'text-ink'
        }`}
      >
        {template.name}
      </h4>
      <p className="text-xs text-ink-muted leading-relaxed">{template.description}</p>
      {isSelected && (
        <div className="mt-3 inline-flex items-center gap-1 rounded-full bg-ink px-2.5 py-0.5 text-2xs font-medium text-white">
          已选择
        </div>
      )}
    </button>
  )
}
