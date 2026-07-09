import { useCallback } from 'react'
import { ArrowLeft, ArrowRight, RotateCcw, Copy, Download } from 'lucide-react'
import { useWorkflowStore } from '../../stores/workflowStore'
import { useAgentStore } from '../../stores/agentStore'
import { NOTE_TEMPLATES, type WorkflowStep, type NoteTemplate } from '../../types'
import { simulateAgentProcessing } from '../../services/agent'
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
        const finalResult = await simulateAgentProcessing(template, content, advanceStage)
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
  const handleCopy = async () => {
    await navigator.clipboard.writeText(result)
    // Brief feedback could be added here
  }

  const handleDownload = () => {
    const blob = new Blob([result], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'notes.md'
    a.click()
    URL.revokeObjectURL(url)
  }

  // ==========================================
  // Step renderers
  // ==========================================
  const renderInputStep = () => (
    <UploadZone value={content} onChange={setContent} />
  )

  const renderConfigStep = () => (
    <div className="animate-fade-in">
      <h3 className="mb-5 text-sm font-medium text-gray-500 uppercase tracking-wide">
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
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
          生成的笔记
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <Copy size={14} />
            复制
          </button>
          <button
            onClick={handleDownload}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-sm text-white hover:bg-primary-700 transition-colors"
          >
            <Download size={14} />
            下载 .md
          </button>
        </div>
      </div>

      {/* Rendered markdown */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 sm:p-8 shadow-sm">
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
      <div className="mt-10 flex items-center justify-between border-t border-gray-200 pt-6">
        <div>
          {step !== 'input' && step !== 'process' && (
            <button
              onClick={prevStep}
              className="inline-flex items-center gap-2 rounded-xl border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
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
              className="inline-flex items-center gap-2 rounded-xl border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
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
                  ? 'bg-primary-600 text-white hover:bg-primary-700 shadow-sm'
                  : 'cursor-not-allowed bg-gray-100 text-gray-400'
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
          ? 'border-primary-400 bg-primary-50 ring-2 ring-primary-100'
          : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50/50'
      }`}
    >
      <div className="mb-2 text-2xl">{template.icon === 'list-tree' ? '🌳' : template.icon === 'file-text' ? '📄' : template.icon === 'layout-panel-top' ? '📋' : '💬'}</div>
      <h4
        className={`mb-1 text-base font-semibold ${
          isSelected ? 'text-primary-700' : 'text-gray-900'
        }`}
      >
        {template.name}
      </h4>
      <p className="text-sm text-gray-500 leading-relaxed">{template.description}</p>
      {isSelected && (
        <div className="mt-3 inline-flex items-center gap-1 rounded-full bg-primary-100 px-2.5 py-0.5 text-xs font-medium text-primary-700">
          已选择
        </div>
      )}
    </button>
  )
}
