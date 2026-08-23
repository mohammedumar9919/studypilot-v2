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
  includeFlat?: boolean
  primary?: 'auto' | 'syllabus' | 'concepts'
  documentIds?: string[]
}

interface UseExamAnalyticsResult {
  data: ExamAnalyticsResponse | null
  loading: boolean
  refreshing: boolean
  error: string | null
  notFound: boolean
  reload: () => void
}

function documentIdsKey(documentIds: string[] | undefined): string {
  if (!documentIds?.length) return ''
  return [...documentIds].sort().join(',')
}

export function useExamAnalytics(
  courseId: string,
  refreshToken = 0,
  options: UseExamAnalyticsOptions = {},
): UseExamAnalyticsResult {
  const {
    sort = 'weightage_desc',
    limit = 50,
    enabled = true,
    includeFlat = false,
    primary = 'auto',
    documentIds,
  } = options
  const idsKey = documentIdsKey(documentIds)
  const [data, setData] = useState<ExamAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const hasDataRef = useRef(false)

  useEffect(() => {
    hasDataRef.current = data != null
  }, [data])

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!trimmed || trimmed.length < 2 || !enabled) {
      setData(null)
      setLoading(false)
      setRefreshing(false)
      setError(null)
      setNotFound(false)
      hasDataRef.current = false
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    if (hasDataRef.current) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)
    setNotFound(false)

    const parsedIds = idsKey ? idsKey.split(',') : undefined

    void fetchExamAnalytics(trimmed, {
      sort,
      limit,
      includeStructure: 'auto',
      primary,
      includeFlat,
      documentIds: parsedIds,
      signal: controller.signal,
    })
      .then((response) => {
        if (controller.signal.aborted) return
        setData(response)
        hasDataRef.current = true
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof ExamAnalyticsApiError && err.status === 404) {
          setNotFound(true)
          setData(null)
          hasDataRef.current = false
          setError(`No exam analytics for course “${trimmed}”.`)
          return
        }
        if (err instanceof DOMException && err.name === 'AbortError') return
        if (!hasDataRef.current) setData(null)
        setError(err instanceof Error ? err.message : 'Could not load exam analytics.')
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
          setRefreshing(false)
        }
      })
  }, [courseId, refreshToken, sort, limit, enabled, includeFlat, primary, idsKey])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  return { data, loading, refreshing, error, notFound, reload: load }
}
