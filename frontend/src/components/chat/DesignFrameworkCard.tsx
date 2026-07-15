import { Sparkles, Clock, BarChart3 } from 'lucide-react'
import type { DesignFrameworkData } from '../../types'

interface Props {
  data: DesignFrameworkData | null | undefined
}

const FORMAT_NAMES: Record<string, string> = {
  outline: '大纲笔记',
  summary: '详细摘要',
  cornell: '康奈尔笔记',
  qa: '问答笔记',
}

export default function DesignFrameworkCard({ data }: Props) {
  if (!data) return null

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-2">
        <Sparkles size={14} className="text-accent-500 flex-shrink-0" />
        <p className="text-xs text-ink-soft">{data.contentSummary}</p>
      </div>

      {/* Topics */}
      {data.topics.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-ink">🎯 核心主题</h4>
          <div className="space-y-2">
            {data.topics.map((t, i) => (
              <div key={i} className="rounded-xl border border-border bg-paper/50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-ink">{t.name}</span>
                  <span className="text-2xs text-ink-muted/60">{t.coverage}</span>
                </div>
                {t.subtopics.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {t.subtopics.map((st, j) => (
                      <span key={j} className="rounded-md bg-primary-50 px-1.5 py-0.5 text-2xs text-primary-600">
                        {st}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Format suggestion */}
      <div className="rounded-xl border border-accent-200 bg-accent-50/50 px-3 py-2.5">
        <h4 className="mb-1 text-xs font-semibold text-ink">📝 推荐格式</h4>
        <p className="text-xs text-ink-soft">
          <span className="font-medium text-accent-700">
            {FORMAT_NAMES[data.suggestedFormat] ?? data.suggestedFormat}
          </span>
          {data.formatReasoning && <span> — {data.formatReasoning}</span>}
        </p>
        {data.alternativeFormats.length > 0 && (
          <p className="mt-1 text-2xs text-ink-muted">
            其他可选：{data.alternativeFormats.map(f => FORMAT_NAMES[f] ?? f).join('、')}
          </p>
        )}
      </div>

      {/* Formatting suggestions */}
      {data.formattingSuggestions.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-ink">💡 格式建议</h4>
          <ul className="space-y-0.5">
            {data.formattingSuggestions.map((s, i) => (
              <li key={i} className="text-xs text-ink-muted flex items-start gap-1.5">
                <span className="text-accent-400 mt-0.5">•</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* User prompts */}
      {data.userPrompts.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-ink">🤔 请告诉我</h4>
          <ul className="space-y-0.5">
            {data.userPrompts.map((p, i) => (
              <li key={i} className="text-xs text-ink-muted flex items-start gap-1.5">
                <span className="text-primary-400 mt-0.5">{i + 1}.</span>
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
