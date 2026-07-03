import { useCallback, useEffect, useRef, useState } from 'react'

import {
  ExamAnalyticsApiError,
  fetchExamAnalytics,
  type ExamAnalyticsResponse,
  type ExamAnalyticsSort,
} from '../api/examAnalyticsClient'

interface UseExamAnalyticsOptions {
  sort?: ExamAnalyticsSort
  limit?: number
  enabled?: boolean
}

interface UseExamAnalyticsResult {
  data: ExamAnalyticsResponse | null
  loading: boolean
  error: string | null
  notFound: boolean
  reload: () => void
}

export function useExamAnalytics(
  courseId: string,
  refreshToken = 0,
  options: UseExamAnalyticsOptions = {},
): UseExamAnalyticsResult {
  const { sort = 'weightage_desc', limit = 50, enabled = true } = options
  const [data, setData] = useState<ExamAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!trimmed || trimmed.length < 2 || !enabled) {
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

    void fetchExamAnalytics(trimmed, {
      sort,
      limit,
      includeStructure: 'auto',
      signal: controller.signal,
    })
      .then((response) => {
        if (controller.signal.aborted) return
        setData(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof ExamAnalyticsApiError && err.status === 404) {
          setNotFound(true)
          setData(null)
          setError(`No exam analytics for course “${trimmed}”.`)
          return
        }
        if (err instanceof DOMException && err.name === 'AbortError') return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load exam analytics.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [courseId, refreshToken, sort, limit, enabled])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  return { data, loading, error, notFound, reload: load }
}
