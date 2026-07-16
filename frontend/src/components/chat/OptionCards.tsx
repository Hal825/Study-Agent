import type { OptionCardsData } from '../../types'

interface Props {
  data: OptionCardsData | null | undefined
  onSelect?: (optionId: string) => void
}

const EMOJI_MAP: Record<string, string> = {
  outline: '🌳',
  summary: '📄',
  cornell: '📋',
  qa: '💬',
}

export default function OptionCards({ data, onSelect }: Props) {
  if (!data) return null

  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-ink">{data.question}</p>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {data.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => onSelect?.(opt.id)}
            className="flex items-start gap-3 rounded-xl border border-border bg-paper/50 p-3.5 text-left hover:border-primary-200 hover:bg-primary-50/30 transition-all duration-150"
          >
            <span className="text-xl flex-shrink-0 mt-0.5">
              {opt.emoji || EMOJI_MAP[opt.id] || '📝'}
            </span>
            <div className="min-w-0">
              <span className="text-sm font-medium text-ink">{opt.label}</span>
              <p className="text-xs text-ink-muted mt-0.5">{opt.description}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
