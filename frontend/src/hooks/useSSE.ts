import { useCallback, useRef, useState } from 'react'

export interface SSEEvent {
  type: string
  data: Record<string, unknown>
}

export function useSSE() {
  const [isConnected, setIsConnected] = useState(false)
  const [currentStage, setCurrentStage] = useState('')
  const [stageIndex, setStageIndex] = useState(0)
  const [result, setResult] = useState('')
  const [isDone, setIsDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Human-in-the-loop state
  const [confirmRequired, setConfirmRequired] = useState(false)
  const [confirmQuestion, setConfirmQuestion] = useState('')
  const [confirmOptions, setConfirmOptions] = useState<string[]>([])
  const [activeSessionId, setActiveSessionId] = useState('')

  /** Reset all processing state before starting a new request */
  const resetState = useCallback(() => {
    setIsConnected(true)
    setCurrentStage('')
    setStageIndex(0)
    setResult('')
    setIsDone(false)
    setError(null)
    setConfirmRequired(false)
    setConfirmQuestion('')
    setConfirmOptions([])
  }, [])

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
            if (line.startsWith('event: ')) {
              continue
            }
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                const event: SSEEvent = { type: data.type, data: data.data }

                switch (event.type) {
                  case 'agent_start':
                    setCurrentStage('正在启动 Agent...')
                    setStageIndex(0)
                    if (event.data.session_id) {
                      setActiveSessionId(event.data.session_id as string)
                    }
                    break
                  case 'stage_change':
                    setCurrentStage(event.data.stage_label as string)
                    setStageIndex(event.data.stage_index as number)
                    break
                  case 'node_finish':
                    break
                  case 'agent_finish':
                    setResult(event.data.result as string)
                    setCurrentStage('')
                    setIsDone(true)
                    setIsConnected(false)
                    break
                  case 'agent_error':
                    setError(event.data.error as string)
                    setCurrentStage('')
                    setIsConnected(false)
                    break
                  case 'human_confirm_required':
                    setConfirmRequired(true)
                    setConfirmQuestion(event.data.question as string)
                    setConfirmOptions((event.data.options as string[]) || [])
                    setCurrentStage('')
                    setIsConnected(false)
                    break
                }
              } catch {
                // skip malformed JSON
              }
              continue
            }
          }
        }

        // Stream ended without agent_finish — treat as error
        if (abortRef.current && !controller.signal.aborted) {
          setError('连接意外中断')
          setIsConnected(false)
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message ?? '连接失败')
          setIsConnected(false)
        }
      })
  }, [resetState])

  // Resume stream after human confirmation
  const confirmAndResume = useCallback((confirmedTemplate: string) => {
    if (!activeSessionId) return
    setConfirmRequired(false)
    setError(null)
    connect(`/api/agent/note/confirm/${activeSessionId}`, {
      template: confirmedTemplate,
    })
  }, [activeSessionId, connect])

  const rejectConfirm = useCallback(() => {
    setConfirmRequired(false)
    setCurrentStage('')
    setError('用户取消了笔记生成')
    setIsConnected(false)
  }, [])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setIsConnected(false)
    setCurrentStage('')
  }, [])

  /** Fully reset all state (abort, clear result, go back to input) */
  const reset = useCallback(() => {
    abortRef.current?.abort()
    setIsConnected(false)
    setCurrentStage('')
    setStageIndex(0)
    setResult('')
    setIsDone(false)
    setError(null)
    setConfirmRequired(false)
    setConfirmQuestion('')
    setConfirmOptions([])
    setActiveSessionId('')
  }, [])

  return {
    isConnected,
    currentStage,
    stageIndex,
    result,
    isDone,
    error,
    confirmRequired,
    confirmQuestion,
    confirmOptions,
    activeSessionId,
    confirmAndResume,
    rejectConfirm,
    connect,
    abort,
    reset,
  }
}
