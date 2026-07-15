import { create } from 'zustand'
import type { ChatMessage, ChatPhase, PreviewMode } from '../types'

interface ChatStore {
  messages: ChatMessage[]
  sessionId: string | null
  phase: ChatPhase
  isStreaming: boolean
  streamingContent: string
  previewMode: PreviewMode
  error: string | null

  addMessage: (msg: ChatMessage) => void
  updateLastMessage: (content: string) => void
  appendStreamChunk: (chunk: string) => void
  clearStreamingContent: () => void
  setSessionId: (id: string) => void
  setPhase: (phase: ChatPhase) => void
  setIsStreaming: (v: boolean) => void
  setPreviewMode: (mode: PreviewMode) => void
  setError: (error: string | null) => void
  clearChat: () => void
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: null,
  phase: 'idle',
  isStreaming: false,
  streamingContent: '',
  previewMode: 'chat',
  error: null,

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (content) =>
    set((s) => {
      const msgs = [...s.messages]
      if (msgs.length > 0) {
        msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content }
      }
      return { messages: msgs }
    }),

  appendStreamChunk: (chunk) =>
    set((s) => ({ streamingContent: s.streamingContent + chunk })),

  clearStreamingContent: () =>
    set({ streamingContent: '' }),

  setSessionId: (id) => set({ sessionId: id }),

  setPhase: (phase) => set({ phase }),

  setIsStreaming: (v) => set({ isStreaming: v }),

  setPreviewMode: (mode) => set({ previewMode: mode }),

  setError: (error) => set({ error, isStreaming: false }),

  clearChat: () =>
    set({
      messages: [],
      sessionId: null,
      phase: 'idle',
      isStreaming: false,
      streamingContent: '',
      previewMode: 'chat',
      error: null,
    }),
}))
