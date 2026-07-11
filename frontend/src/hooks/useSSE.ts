import { useCallback, useRef, useState } from 'react'

export interface SSEEvent {
  type: string
  data: Record<string, unknown>
}

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void
  onError?: (error: string) => void
}

export function useSSE() {
  const [isConnected, setIsConnected] = useState(false)
  const [currentStage, setCurrentStage] = useState('')
  const [stageIndex, setStageIndex] = useState(0)
  const [result, setResult] = useState('')
  const [isDone, setIsDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const connect = useCallback((url: string, body: unknown) => {
    // Reset state
    setIsConnected(true)
    setCurrentStage('')
    setStageIndex(0)
    setResult('')
    setIsDone(false)
    setError(null)

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
              const eventType = line.slice(7).trim()
              continue  // eslint-disable-line
            }
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                const event: SSEEvent = { type: data.type, data: data.data }

                // Update state based on event type
                switch (event.type) {
                  case 'agent_start':
                    setCurrentStage('正在启动 Agent...')
                    setStageIndex(0)
                    break
                  case 'stage_change':
                    setCurrentStage(event.data.stage_label as string)
                    setStageIndex(event.data.stage_index as number)
                    break
                  case 'node_finish':
                    // Stage already set by stage_change
                    break
                  case 'agent_finish':
                    setResult(event.data.result as string)
                    setCurrentStage('')
                    setIsDone(true)
                    setIsConnected(false)
                    break
                  case 'agent_error':
                    setError(event.data.error as string)
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
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message ?? '连接失败')
          setIsConnected(false)
        }
      })

    return () => {
      controller.abort()
      setIsConnected(false)
    }
  }, [])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setIsConnected(false)
  }, [])

  return {
    isConnected,
    currentStage,
    stageIndex,
    result,
    isDone,
    error,
    connect,
    abort,
  }
}
