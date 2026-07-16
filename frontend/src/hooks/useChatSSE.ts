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
        const content = (payload.content as string) || ''
        const role = payload.role as string

        // Suppress redundant messages that duplicate the design framework card
        if (role === 'assistant') {
          // "我已经分析了你的学习内容..." — duplicates the design framework card
          if (content.startsWith('我已经分析了你的学习内容')) break
          // "你还可以告诉我：你想重点关注..." — duplicates user prompts in design card
          if (content.startsWith('你还可以告诉我')) break
        }

        const msg: ChatMessage = {
          id: `msg-${Date.now()}`,
          role: (payload.role as 'user' | 'assistant' | 'system') || 'assistant',
          type: (payload.message_type as ChatMessage['type']) || 'text',
          content,
          data: null,
          timestamp: Date.now(),
        }
        store.addMessage(msg)
        break
      }

      case 'chat_design_framework': {
        // Agent has finished analyzing, now at HITL #1 — waiting for user preferences
        store.setPhase('design')
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
        // First chunk → we're generating
        if (store.phase !== 'generating' && store.phase !== 'revising') {
          store.setPhase('generating')
        }
        // Auto-switch to split view on first chunk if in chat mode
        if (store.previewMode === 'chat') {
          store.setPreviewMode('split')
        }
        break
      }

      case 'chat_note_result': {
        // Agent has finished generating, now at HITL #2 — waiting for user feedback
        store.setPhase('result')
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
    // Abort any existing stream before starting a new one
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }

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

        // Stream completed naturally — ensure isStreaming is false
        if (!controller.signal.aborted) {
          store.setIsStreaming(false)
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          store.setError(err.message ?? '连接失败')
        }
        // Always clean up streaming state on error
        if (!controller.signal.aborted) {
          store.setIsStreaming(false)
        }
      })
  }, [resetState, processSSE, store])

  const startSession = useCallback((content: string, fileName?: string, fileSize?: number) => {
    // Add user message to chat immediately
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      type: 'text',
      content: content.length > 500 ? content.slice(0, 500) + '\n\n...（内容已截断）' : content,
      timestamp: Date.now(),
      fileName,
      fileSize,
    }
    store.addMessage(userMsg)
    store.setPhase('analyzing')
    connect('/api/chat/stream', { content })
  }, [store, connect])

  const sendMessage = useCallback((message: string, selections?: SelectionsData, fileInfo?: { name: string; size: number }) => {
    const sessionId = store.sessionId
    if (!sessionId) {
      // Fallback: no session yet, start a new one
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        type: 'text',
        content: message,
        timestamp: Date.now(),
        fileName: fileInfo?.name,
        fileSize: fileInfo?.size,
      }
      store.addMessage(userMsg)
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
      fileName: fileInfo?.name,
      fileSize: fileInfo?.size,
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
