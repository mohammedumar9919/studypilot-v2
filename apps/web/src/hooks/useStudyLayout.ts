import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchStudyLayout, StudyLayoutApiError } from '../api/studyLayoutClient'
import type { StudyLayoutResponse } from '../types'

interface UseStudyLayoutResult {
  data: StudyLayoutResponse | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useStudyLayout(courseId: string, refreshToken = 0): UseStudyLayoutResult {
  const [data, setData] = useState<StudyLayoutResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!trimmed || trimmed.length < 2) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    void fetchStudyLayout(trimmed, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setData(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setData(null)
        if (err instanceof StudyLayoutApiError) {
          setError(`${err.status}: ${err.message}`)
        } else {
          setError(err instanceof Error ? err.message : 'Could not load study layout.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [courseId, refreshToken])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  return { data, loading, error, reload: load }
}
