import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchTopicFrequency, TopicFrequencyApiError } from '../api/topicFrequencyClient'
import type { TopicFrequencyResponse } from '../types'

interface UseTopicFrequencyOptions {
  sectionDetail?: boolean
}

interface UseTopicFrequencyResult {
  data: TopicFrequencyResponse | null
  loading: boolean
  error: string | null
  notFound: boolean
  reload: () => void
}

export function useTopicFrequency(
  courseId: string,
  refreshToken = 0,
  options: UseTopicFrequencyOptions = {},
): UseTopicFrequencyResult {
  const { sectionDetail = false } = options
  const [data, setData] = useState<TopicFrequencyResponse | null>(null)
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

    void fetchTopicFrequency(trimmed, { sectionDetail, signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return
        setData(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof TopicFrequencyApiError && err.status === 404) {
          setNotFound(true)
          setData(null)
          setError(`No exam data for course “${trimmed}”.`)
          return
        }
        if (err instanceof DOMException && err.name === 'AbortError') return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load topic frequency.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [courseId, refreshToken, sectionDetail])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  return { data, loading, error, notFound, reload: load }
}
