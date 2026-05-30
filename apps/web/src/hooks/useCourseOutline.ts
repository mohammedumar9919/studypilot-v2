import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchCourseOutline, OutlineApiError } from '../api/outlineClient'
import type { OutlineResponse } from '../types'

interface UseCourseOutlineResult {
  data: OutlineResponse | null
  loading: boolean
  error: string | null
  notFound: boolean
  reload: () => void
}

export function useCourseOutline(courseId: string): UseCourseOutlineResult {
  const [data, setData] = useState<OutlineResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!trimmed) {
      setData(null)
      setLoading(false)
      setError('Enter a course ID to load the course outline.')
      setNotFound(false)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setNotFound(false)

    void fetchCourseOutline(trimmed, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setData(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof OutlineApiError && err.status === 404) {
          setNotFound(true)
          setData(null)
          setError(`No outline for course “${trimmed}”.`)
          return
        }
        if (err instanceof DOMException && err.name === 'AbortError') return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load course outline.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
  }, [courseId])

  useEffect(() => {
    load()
    return () => abortRef.current?.abort()
  }, [load])

  return { data, loading, error, notFound, reload: load }
}
