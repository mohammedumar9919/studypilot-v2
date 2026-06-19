import { useCallback, useEffect, useRef, useState } from 'react'

import { postStudyQuery, postStudyQueryStream, QueryApiError } from '../api/queryClient'
import { RETRIEVAL_ESTIMATE_MS } from '../constants/goldenMisses'
import type { QueryRequest, QueryResponse, QueryStage } from '../types'

interface SubmitOptions {
  useStream?: boolean
}

interface UseStudyQueryResult {
  stage: QueryStage
  elapsedMs: number
  result: QueryResponse | null
  error: string | null
  streamNotice: string | null
  submit: (request: QueryRequest, options?: SubmitOptions) => Promise<void>
  reset: () => void
}

export function useStudyQuery(): UseStudyQueryResult {
  const [stage, setStage] = useState<QueryStage>('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [streamNotice, setStreamNotice] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<number | null>(null)
  const startRef = useRef<number>(0)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const startElapsedTimer = useCallback(
    (useHeuristicStage: boolean) => {
      startRef.current = Date.now()
      setElapsedMs(0)
      clearTimer()
      timerRef.current = window.setInterval(() => {
        const elapsed = Date.now() - startRef.current
        setElapsedMs(elapsed)
        if (useHeuristicStage && elapsed >= RETRIEVAL_ESTIMATE_MS) {
          setStage((current) => (current === 'retrieving' ? 'generating' : current))
        }
      }, 250)
    },
    [clearTimer],
  )

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    clearTimer()
    setStage('idle')
    setElapsedMs(0)
    setResult(null)
    setError(null)
    setStreamNotice(null)
  }, [clearTimer])

  useEffect(
    () => () => {
      abortRef.current?.abort()
      clearTimer()
    },
    [clearTimer],
  )

  const runNonStreamQuery = useCallback(
    async (body: QueryRequest, controller: AbortController) => {
      const response = await postStudyQuery(body, controller.signal)
      if (controller.signal.aborted) return
      setResult(response)
      setStage('done')
    },
    [],
  )

  const submit = useCallback(
    async (request: QueryRequest, options?: SubmitOptions) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const body: QueryRequest = request
      const useStream = options?.useStream ?? false

      setResult(null)
      setError(null)
      setStreamNotice(null)
      setStage('retrieving')
      startElapsedTimer(!useStream)

      const runFallback = async (notice: string) => {
        if (controller.signal.aborted) return
        setStreamNotice(notice)
        setStage('retrieving')
        setResult(null)
        startElapsedTimer(true)
        await runNonStreamQuery(body, controller)
      }

      try {
        if (useStream) {
          let sawDone = false

          await postStudyQueryStream(
            body,
            {
              onRetrievalComplete: (payload) => {
                if (controller.signal.aborted) return
                setStage('generating')
                setResult({
                  status: 'ok',
                  answer: '',
                  sources: payload.sources,
                  rerank_scores: payload.rerank_scores,
                  retrieval_debug: payload.retrieval_debug,
                })
              },
              onToken: ({ delta }) => {
                if (controller.signal.aborted) return
                setStage('generating')
                setResult((current) => {
                  if (!current || current.status !== 'ok') {
                    return {
                      status: 'ok',
                      answer: delta,
                      sources: [],
                      rerank_scores: [],
                      retrieval_debug: null,
                    }
                  }
                  return {
                    ...current,
                    answer: `${current.answer ?? ''}${delta}`,
                  }
                })
              },
              onDone: (payload) => {
                if (controller.signal.aborted) return
                sawDone = true
                setResult(payload)
                setStage('done')
              },
              onError: ({ detail, status_code }) => {
                if (controller.signal.aborted) return
                throw new QueryApiError(detail, status_code ?? 502)
              },
            },
            controller.signal,
          )

          if (!sawDone && !controller.signal.aborted) {
            throw new Error('Stream ended before done event')
          }
        } else {
          await runNonStreamQuery(body, controller)
        }
      } catch (err) {
        if (controller.signal.aborted) return

        if (useStream) {
          try {
            await runFallback('Live stream unavailable — using standard query.')
            return
          } catch (fallbackErr) {
            if (controller.signal.aborted) return
            if (fallbackErr instanceof QueryApiError) {
              setError(`${fallbackErr.status}: ${fallbackErr.message}`)
            } else if (fallbackErr instanceof DOMException && fallbackErr.name === 'AbortError') {
              return
            } else {
              setError(
                fallbackErr instanceof Error ? fallbackErr.message : 'Query failed after stream fallback',
              )
            }
            setStage('error')
            return
          }
        }

        if (err instanceof QueryApiError) {
          setError(`${err.status}: ${err.message}`)
        } else if (err instanceof DOMException && err.name === 'AbortError') {
          return
        } else {
          setError(err instanceof Error ? err.message : 'Query failed')
        }
        setStage('error')
      } finally {
        clearTimer()
        abortRef.current = null
      }
    },
    [clearTimer, runNonStreamQuery, startElapsedTimer],
  )

  return { stage, elapsedMs, result, error, streamNotice, submit, reset }
}
