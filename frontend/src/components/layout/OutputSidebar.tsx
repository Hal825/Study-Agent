import { useState } from 'react'
import { Trash2, Download, Eye, FileText, Clock, X, ChevronDown } from 'lucide-react'
import { useOutputStore, type OutputItem } from '../../stores/outputStore'
import { markdownToPlainText, downloadAsPDF, downloadAsDocx } from '../../services/agent'

const TEMPLATE_LABELS: Record<string, string> = {
  outline: '大纲笔记',
  summary: '详细摘要',
  cornell: '康奈尔笔记',
  qa: '问答笔记',
}

const TEMPLATE_COLORS: Record<string, string> = {
  outline: 'bg-emerald-50 text-emerald-700',
  summary: 'bg-blue-50 text-blue-700',
  cornell: 'bg-violet-50 text-violet-700',
  qa: 'bg-amber-50 text-amber-700',
}

function relativeTime(ts: number): string {
  const seconds = Math.floor((Date.now() - ts) / 1000)
  if (seconds < 60) return '刚刚'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`
  return `${Math.floor(seconds / 86400)} 天前`
}

export default function OutputSidebar({ onClose }: { onClose: () => void }) {
  const [previewId, setPreviewId] = useState<string | null>(null)
  const { outputs, removeOutput, clearAll } = useOutputStore()

  const previewItem = outputs.find((o) => o.id === previewId)

  return (
    <>
      <aside className="flex w-72 flex-col border-l border-border bg-surface overflow-hidden animate-slide-in-right">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <FileText size={14} className="text-ink-muted" />
            <span className="text-sm font-medium text-ink-soft">输出历史</span>
            {outputs.length > 0 && (
              <span className="rounded-md bg-paper-dark px-1.5 py-0.5 text-xs text-ink-muted">
                {outputs.length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-0.5">
            {outputs.length > 0 && (
              <button
                onClick={clearAll}
                className="rounded-lg p-1.5 text-ink-muted/40 hover:bg-paper-dark hover:text-ink-soft transition-colors"
                title="清空全部"
              >
                <Trash2 size={13} />
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-ink-muted/40 hover:bg-paper-dark hover:text-ink-soft transition-colors"
              title="关闭"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {outputs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-ink-muted/30">
              <Clock size={24} className="mb-3" />
              <p className="text-xs">暂无输出</p>
              <p className="text-xs mt-1">生成笔记后将在这里显示</p>
            </div>
          ) : (
            <div className="divide-y divide-border-light">
              {outputs.map((item) => (
                <OutputCard
                  key={item.id}
                  item={item}
                  onPreview={() => setPreviewId(item.id)}
                  onDelete={() => removeOutput(item.id)}
                />
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Preview modal */}
      {previewItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-sm"
          onClick={() => setPreviewId(null)}
        >
          <div
            className="relative mx-4 max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-surface p-6 shadow-panel animate-slide-up scrollbar-thin"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`rounded-lg px-2 py-0.5 text-xs font-medium ${TEMPLATE_COLORS[previewItem.template] ?? 'bg-paper-dark text-ink-muted'}`}>
                  {TEMPLATE_LABELS[previewItem.template] ?? previewItem.template}
                </span>
                <span className="text-xs text-ink-muted">{relativeTime(previewItem.createdAt)}</span>
              </div>
              <button
                onClick={() => setPreviewId(null)}
                className="rounded-lg p-1.5 text-ink-muted/40 hover:bg-paper-dark hover:text-ink-soft transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <h3 className="text-lg font-semibold text-ink mb-4 font-display">{previewItem.title}</h3>
            <div className="text-sm text-ink-soft leading-relaxed whitespace-pre-wrap">
              {previewItem.content.slice(0, 5000)}
              {previewItem.content.length > 5000 && (
                <p className="text-ink-muted mt-4 text-xs">...（内容已截断）</p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function OutputCard({
  item,
  onPreview,
  onDelete,
}: {
  item: OutputItem
  onPreview: () => void
  onDelete: () => void
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const doDownload = async (format: string) => {
    setDropdownOpen(false)
    const filename = item.title.replace(/[^\w一-鿿]/g, '_').slice(0, 30)
    switch (format) {
      case 'md': {
        const blob = new Blob([item.content], { type: 'text/markdown' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a'); a.href = url; a.download = `${filename}.md`; a.click()
        URL.revokeObjectURL(url)
        break
      }
      case 'txt': {
        const text = markdownToPlainText(item.content)
        const blob = new Blob([text], { type: 'text/plain' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a'); a.href = url; a.download = `${filename}.txt`; a.click()
        URL.revokeObjectURL(url)
        break
      }
      case 'pdf':
        downloadAsPDF(item.content, filename)
        break
      case 'docx':
        try { await downloadAsDocx(item.content, filename) }
        catch { alert('Word 导出失败，请确保后端服务已启动') }
        break
    }
  }

  return (
    <div className="px-3 py-3 hover:bg-paper/60 transition-colors">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <button
            onClick={onPreview}
            className="text-sm font-medium text-ink text-left truncate w-full hover:text-primary-600 transition-colors"
          >
            {item.title}
          </button>
          <div className="mt-1 flex items-center gap-1.5">
            <span className={`rounded-md px-1.5 py-0.5 text-xs font-medium ${TEMPLATE_COLORS[item.template] ?? ''}`}>
              {TEMPLATE_LABELS[item.template] ?? item.template}
            </span>
            <span className="text-xs text-ink-muted/50">{relativeTime(item.createdAt)}</span>
          </div>
        </div>

        <div className="flex items-center gap-0.5 flex-shrink-0">
          <button onClick={onPreview} className="rounded-lg p-1 text-ink-muted/30 hover:bg-paper-dark hover:text-ink-soft transition-colors" title="预览">
            <Eye size={13} />
          </button>

          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="rounded-lg p-1 text-ink-muted/30 hover:bg-paper-dark hover:text-ink-soft transition-colors flex items-center gap-0.5"
              title="下载"
            >
              <Download size={13} />
              <ChevronDown size={9} />
            </button>
            {dropdownOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setDropdownOpen(false)} />
                <div className="absolute right-0 top-7 z-20 w-36 rounded-2xl border border-border bg-surface py-1 shadow-panel animate-fade-in">
                  {[
                    { label: 'Markdown (.md)', value: 'md' },
                    { label: '纯文本 (.txt)', value: 'txt' },
                    { label: 'PDF', value: 'pdf' },
                    { label: 'Word (.docx)', value: 'docx' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => doDownload(opt.value)}
                      className="w-full px-3 py-1.5 text-left text-xs text-ink-soft hover:bg-paper-dark transition-colors"
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <button onClick={onDelete} className="rounded-lg p-1 text-ink-muted/30 hover:bg-paper-dark hover:text-ink-soft transition-colors" title="删除">
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}
