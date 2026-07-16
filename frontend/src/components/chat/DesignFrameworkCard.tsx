import { Sparkles, Target, FileText, Lightbulb } from 'lucide-react'
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

const FORMAT_DESCRIPTIONS: Record<string, string> = {
  outline: '层次分明的结构化笔记，适合梳理知识体系',
  summary: '连贯的段落式总结，适合深入理解内容',
  cornell: '分区式笔记法：线索栏 + 笔记栏 + 总结栏',
  qa: '以问答形式组织知识，适合备考和自测',
}

export default function DesignFrameworkCard({ data }: Props) {
  if (!data) return null

  const suggestedFmtName = FORMAT_NAMES[data.suggestedFormat] ?? data.suggestedFormat
  const suggestedFmtDesc = FORMAT_DESCRIPTIONS[data.suggestedFormat] ?? ''
  const alternativeNames = data.alternativeFormats
    .filter(f => f !== data.suggestedFormat)
    .map(f => FORMAT_NAMES[f] ?? f)

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center gap-2.5 pb-3 border-b border-border/60">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-100">
          <Sparkles size={16} className="text-accent-500" />
        </div>
        <div>
          <p className="text-sm font-semibold text-ink">初步设计稿</p>
          <p className="text-xs text-ink-muted">基于内容分析生成的结构化方案</p>
        </div>
      </div>

      {/* ── Section 1: 主题分析 ── */}
      <SectionBlock
        icon={<Target size={15} />}
        iconBg="bg-sky-50 text-sky-600"
        title="内容主题分析"
        subtitle={data.contentSummary}
      >
        {data.topics.length > 0 && (
          <div className="space-y-2">
            {data.topics.slice(0, 5).map((t, i) => (
              <div key={i} className="flex items-start gap-3 rounded-xl border border-border bg-paper/50 px-3.5 py-2.5">
                <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-md bg-primary-50 text-xs font-semibold text-primary-600 mt-0.5">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-medium text-ink">{t.name}</span>
                    <span className="text-xs text-ink-muted/60">{t.coverage}</span>
                  </div>
                  {t.subtopics.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {t.subtopics.map((st, j) => (
                        <span key={j} className="rounded-md bg-sky-50 px-1.5 py-0.5 text-xs text-sky-700">
                          {st}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionBlock>

      {/* ── Section 2: 格式设计 ── */}
      <SectionBlock
        icon={<FileText size={15} />}
        iconBg="bg-violet-50 text-violet-600"
        title="推荐笔记格式"
        subtitle={`根据内容结构，推荐使用「${suggestedFmtName}」格式`}
      >
        <div className="rounded-xl border border-violet-200 bg-violet-50/40 px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="rounded-md bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-700">
              {suggestedFmtName}
            </span>
            {data.formatReasoning && (
              <span className="text-xs text-violet-600/70">{data.formatReasoning}</span>
            )}
          </div>
          <p className="text-sm text-ink-soft">{suggestedFmtDesc}</p>
          {alternativeNames.length > 0 && (
            <p className="mt-2 text-xs text-ink-muted">
              其他可选格式：{alternativeNames.join('、')}
            </p>
          )}
        </div>
      </SectionBlock>

      {/* ── Section 3: 优化建议 ── */}
      {data.formattingSuggestions.length > 0 && (
        <SectionBlock
          icon={<Lightbulb size={15} />}
          iconBg="bg-amber-50 text-amber-600"
          title="格式优化建议"
          subtitle="以下建议可让笔记更清晰易读"
        >
          <ul className="space-y-1.5">
            {data.formattingSuggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-soft">
                <span className="flex-shrink-0 mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-400" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </SectionBlock>
      )}

      {/* ── User prompts ── */}
      {data.userPrompts.length > 0 && (
        <div className="rounded-xl border border-border bg-paper-dark/50 px-4 py-3">
          <p className="text-xs font-medium text-ink-muted mb-2">在继续之前，请告诉我：</p>
          <ul className="space-y-1">
            {data.userPrompts.map((p, i) => (
              <li key={i} className="text-sm text-ink-soft flex items-start gap-2">
                <span className="flex-shrink-0 text-accent-400 font-medium">{i + 1}.</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Section wrapper ──
function SectionBlock({
  icon,
  iconBg,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode
  iconBg: string
  title: string
  subtitle: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-2.5 mb-2.5">
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${iconBg}`}>
          {icon}
        </div>
        <div>
          <h4 className="text-sm font-semibold text-ink">{title}</h4>
          <p className="text-xs text-ink-muted">{subtitle}</p>
        </div>
      </div>
      {children}
    </div>
  )
}
