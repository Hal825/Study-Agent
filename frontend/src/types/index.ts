// ============================================================
// 笔记模板类型
// ============================================================
export interface NoteTemplate {
  id: string
  name: string
  description: string
  icon: string
  prompt: string
}

export const NOTE_TEMPLATES: NoteTemplate[] = [
  {
    id: 'outline',
    name: '大纲笔记',
    description: '层次分明的结构化笔记，适合梳理知识体系',
    icon: 'list-tree',
    prompt: '请将以下内容整理为层次分明的大纲笔记，使用多级标题和列表结构，突出重点概念和关键信息。',
  },
  {
    id: 'summary',
    name: '详细摘要',
    description: '连贯的段落式总结，适合深入理解内容',
    icon: 'file-text',
    prompt: '请将以下内容整理为详细摘要笔记，用连贯的段落总结核心内容，保留重要的细节和数据。',
  },
  {
    id: 'cornell',
    name: '康奈尔笔记',
    description: '分区式笔记法：线索栏 + 笔记栏 + 总结栏',
    icon: 'layout-panel-top',
    prompt: '请将以下内容整理为康奈尔笔记格式，分为三部分：线索栏（关键词/问题）、笔记栏（主要内容）、总结栏（用自己的话概括）。',
  },
  {
    id: 'qa',
    name: '问答笔记',
    description: '以问答形式组织知识，适合备考和自测',
    icon: 'message-circle-question',
    prompt: '请将以下内容整理为问答形式的笔记，提炼出关键问题并给出详细答案，方便后续复习和自测。',
  },
]

// ============================================================
// 导航工具定义
// ============================================================
export interface ToolNavItem {
  id: string
  name: string
  description: string
  icon: string
  path: string
  available: boolean
  badge?: string
}

export const TOOLS: ToolNavItem[] = [
  {
    id: 'chat',
    name: 'AI 学习对话',
    description: '与 AI 对话，逐步确认需求，自动生成结构化笔记',
    icon: 'message-circle',
    path: '/chat',
    available: true,
  },
  {
    id: 'knowledge-graph',
    name: '知识图谱',
    description: '自动提取知识实体及其关联，构建可视化知识网络',
    icon: 'git-graph',
    path: '/tool/knowledge-graph',
    available: false,
    badge: '即将推出',
  },
  {
    id: 'qa',
    name: '智能问答',
    description: '基于学习内容，生成高质量问答对，辅助记忆',
    icon: 'brain',
    path: '/tool/qa',
    available: false,
    badge: '即将推出',
  },
]

// ============================================================
// Chat 对话类型
// ============================================================
export type MessageRole = 'user' | 'assistant' | 'system'
export type MessageType = 'text' | 'design_framework' | 'option_cards' | 'markdown_note'
export type ChatPhase = 'idle' | 'analyzing' | 'design' | 'generating' | 'revising' | 'done'
export type PreviewMode = 'chat' | 'split' | 'preview'

export interface TopicItem {
  name: string
  coverage: string
  subtopics: string[]
}

export interface DesignFrameworkData {
  contentSummary: string
  topics: TopicItem[]
  suggestedFormat: string
  formatReasoning?: string
  alternativeFormats: string[]
  formattingSuggestions: string[]
  userPrompts: string[]
}

export interface OptionCard {
  id: string
  label: string
  description: string
  emoji: string
}

export interface OptionCardsData {
  question: string
  options: OptionCard[]
  multiSelect: boolean
}

export interface ChatMessage {
  id: string
  role: MessageRole
  type: MessageType
  content: string
  data?: DesignFrameworkData | OptionCardsData | null
  timestamp: number
}

export interface SelectionsData {
  template?: string
  annotations?: boolean
  color_emphasis?: boolean
  format_modifications?: string
  topics?: string[]
}
