import { GraduationCap, User } from 'lucide-react'
import type { ChatMessage as ChatMessageType } from '../../types'
import MarkdownRenderer from '../common/MarkdownRenderer'
import DesignFrameworkCard from './DesignFrameworkCard'
import OptionCards from './OptionCards'

interface Props {
  message: ChatMessageType
  onOptionSelect?: (optionId: string) => void
}

export default function ChatMessage({ message, onOptionSelect }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 mb-5 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-xl ${
        isUser
          ? 'bg-primary-100 text-primary-500'
          : 'bg-accent-100 text-accent-600'
      }`}>
        {isUser ? <User size={15} /> : <GraduationCap size={15} />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[80%] min-w-0 ${
        isUser ? 'items-end' : 'items-start'
      }`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary-50 text-ink rounded-tr-md'
            : 'bg-surface border border-border text-ink-soft rounded-tl-md shadow-card'
        }`}>
          {message.type === 'markdown_note' ? (
            <div className="max-h-96 overflow-y-auto scrollbar-thin">
              <MarkdownRenderer content={message.content} />
            </div>
          ) : message.type === 'design_framework' ? (
            <DesignFrameworkCard data={message.data as any} />
          ) : message.type === 'option_cards' ? (
            <OptionCards
              data={message.data as any}
              onSelect={onOptionSelect}
            />
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>
        <p className={`mt-1 text-2xs text-ink-muted/40 ${
          isUser ? 'text-right' : ''
        }`}>
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  )
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
