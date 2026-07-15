import { useCallback, useRef } from 'react'
import { useChatStore } from '../stores/chatStore'
import { useOutputStore } from '../stores/outputStore'
import type { ChatMessage, SelectionsData } from '../types'

export function useChatSSE() {
  const store = useChatStore()
  const addOutput = useOutputStore((s) => s.addOutput)
  const abortRef = useRef<AbortController | null>(null)

  const resetState = useCallback(() => {
    store.setIsStreaming(true)
    store.setError(null)
    store.clearStreamingContent()
  }, [store])

  const processSSE = useCallback((data: Record<string, unknown>) => {
    const eventType = data.type as string
    const payload = data.data as Record<string, unknown>

    // Always capture session_id from any event if not yet set
    if (!store.sessionId && payload.session_id) {
      store.setSessionId(payload.session_id as string)
    }

    switch (eventType) {
      case 'chat_message': {
        const msg: ChatMessage = {
          id: `msg-${Date.now()}`,
          role: (payload.role as 'user' | 'assistant' | 'system') || 'assistant',
          type: (payload.message_type as ChatMessage['type']) || 'text',
          content: (payload.content as string) || '',
          data: null,
          timestamp: Date.now(),
        }
        store.addMessage(msg)
        break
      }

      case 'chat_design_framework': {
        const df = payload.design_framework as Record<string, unknown>
        const msg: ChatMessage = {
          id: `df-${Date.now()}`,
          role: 'assistant',
          type: 'design_framework',
          content: '',
          data: df ? {
            contentSummary: (df.content_summary as string) || '',
            topics: (df.topics as DesignFrameworkData['topics']) || [],
            suggestedFormat: (df.suggested_format as string) || 'outline',
            formatReasoning: (df.format_reasoning as string) || '',
            alternativeFormats: (df.alternative_formats as string[]) || [],
            formattingSuggestions: (df.formatting_suggestions as string[]) || [],
            userPrompts: (df.user_prompts as string[]) || [],
          } : null,
          timestamp: Date.now(),
        }
        store.addMessage(msg)
        break
      }

      case 'chat_option_cards': {
        const msg: ChatMessage = {
          id: `opts-${Date.now()}`,
          role: 'assistant',
          type: 'option_cards',
          content: (payload.question as string) || '',
          data: {
            question: (payload.question as string) || '',
            options: (payload.options as OptionCard[]) || [],
            multiSelect: (payload.multi_select as boolean) || false,
          },
          timestamp: Date.now(),
        }
        store.addMessage(msg)
        break
      }

      case 'chat_stream_chunk': {
        const chunk = (payload.chunk as string) || ''
        store.appendStreamChunk(chunk)
        // Auto-switch to split view on first chunk if in chat mode
        if (store.previewMode === 'chat') {
          store.setPreviewMode('split')
        }
        break
      }

      case 'chat_note_result': {
        const noteMd = (payload.note_markdown as string) || ''
        const templateId = (payload.template_id as string) || 'outline'
        const msg: ChatMessage = {
          id: `note-${Date.now()}`,
          role: 'assistant',
          type: 'markdown_note',
          content: noteMd,
          data: null,
          timestamp: Date.now(),
        }
        store.addMessage(msg)
        // Save to output history
        const title = noteMd.trim().split('\n')[0]?.replace(/^#+\s*/, '').trim().slice(0, 60) || '未命名笔记'
        addOutput(templateId, noteMd)
        break
      }

      case 'chat_done': {
        store.setIsStreaming(false)
        store.setPhase('done')
        break
      }

      case 'agent_error': {
        store.setError((payload.error as string) || '未知错误')
        break
      }

      // Ignore old progress events gracefully
      case 'chat_progress':
      case 'stage_change':
        break
    }
  }, [store, addOutput])

  const connect = useCallback((url: string, body: unknown) => {
    resetState()

    const controller = new AbortController()
    abortRef.current = controller

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: response.statusText }))
          throw new Error(err.detail ?? `请求失败 (${response.status})`)
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error('无法读取响应流')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (line.startsWith('event: ')) continue
            if (line.startsWith('data: ')) {
              try {
                const parsed = JSON.parse(line.slice(6))
                processSSE(parsed)
              } catch { /* skip malformed JSON */ }
            }
          }
        }

        // Stream ended
        if (!controller.signal.aborted) {
          store.setIsStreaming(false)
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          store.setError(err.message ?? '连接失败')
        }
      })
  }, [resetState, processSSE, store])

  const startSession = useCallback((content: string) => {
    store.setPhase('analyzing')
    connect('/api/chat/stream', { content })
  }, [store, connect])

  const sendMessage = useCallback((message: string, selections?: SelectionsData) => {
    const sessionId = store.sessionId
    if (!sessionId) {
      // Fallback: if sessionId not set yet, treat as new session with content
      store.setPhase('analyzing')
      connect('/api/chat/stream', { content: message })
      return
    }

    // Add user message immediately
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      type: 'text',
      content: message,
      timestamp: Date.now(),
    }
    store.addMessage(userMsg)

    // Determine phase based on current state
    const currentPhase = store.phase
    if (currentPhase === 'done') {
      store.setPhase('revising')
    } else {
      store.setPhase('generating')
    }

    connect(`/api/chat/confirm/${sessionId}`, {
      message,
      selections: selections || {},
    })
  }, [store, connect])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    store.setIsStreaming(false)
  }, [store])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    store.clearChat()
  }, [store])

  return {
    startSession,
    sendMessage,
    abort,
    reset,
  }
}

// Inline types to avoid circular imports
interface OptionCard {
  id: string
  label: string
  description: string
  emoji: string
}

interface DesignFrameworkData {
  contentSummary: string
  topics: { name: string; coverage: string; subtopics: string[] }[]
  suggestedFormat: string
  formatReasoning?: string
  alternativeFormats: string[]
  formattingSuggestions: string[]
  userPrompts: string[]
}
