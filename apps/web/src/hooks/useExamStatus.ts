import { useCallback, useEffect, useRef, useState } from 'react'

import { ExamStatusApiError, fetchExamStatus } from '../api/examStatusClient'
import type { ExamStatusResponse } from '../types'

interface UseExamStatusResult {
  data: ExamStatusResponse | null
  loading: boolean
  error: string | null
  notFound: boolean
  examIndexReady: boolean | null
  heatmapAvailable: boolean | null
  reload: () => void
}

export function useExamStatus(courseId: string, refreshToken = 0): UseExamStatusResult {
  const [data, setData] = useState<ExamStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!trimmed || trimmed.length < 2) {
      setData(null)
      setLoading(false)
      setError(null)
      setNotFound(false)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setNotFound(false)
    setData(null)

    void fetchExamStatus(trimmed, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setData(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof ExamStatusApiError && err.status === 404) {
          setNotFound(true)
          setData(null)
          setError(`No exam status for course “${trimmed}”.`)
          return
        }
        if (err instanceof DOMException && err.name === 'AbortError') return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load exam status.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [courseId, refreshToken])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  const examIndexReady = loading ? null : (data?.exam_index_ready ?? false)
  const heatmapAvailable = loading ? null : (data?.heatmap_available ?? false)

  return { data, loading, error, notFound, examIndexReady, heatmapAvailable, reload: load }
}
