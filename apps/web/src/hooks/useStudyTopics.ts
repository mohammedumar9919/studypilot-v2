import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchStudyTopics, StudyTopicsApiError } from '../api/studyTopicsClient'
import type { StudyTopic } from '../types'

interface UseStudyTopicsResult {
  topics: StudyTopic[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function useStudyTopics(
  courseId: string,
  refreshToken = 0,
  enabled = true,
): UseStudyTopicsResult {
  const [topics, setTopics] = useState<StudyTopic[]>([])
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!enabled || !trimmed || trimmed.length < 2) {
      setTopics([])
      setLoading(false)
      setError(null)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    void fetchStudyTopics(trimmed, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setTopics(response.topics)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setTopics([])
        if (err instanceof StudyTopicsApiError) {
          setError(`${err.status}: ${err.message}`)
        } else {
          setError(err instanceof Error ? err.message : 'Could not load study topics.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [courseId, enabled, refreshToken])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  return { topics, loading, error, reload: load }
}
