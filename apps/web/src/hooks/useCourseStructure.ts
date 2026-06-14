import { useCallback, useEffect, useState } from 'react'

import {
  CourseStructureApiError,
  fetchCourseStructure,
} from '../api/courseStructureClient'
import type { CourseStructureResponse } from '../types'

interface UseCourseStructureResult {
  data: CourseStructureResponse | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useCourseStructure(
  courseId: string,
  refreshToken: number,
  enabled: boolean,
): UseCourseStructureResult {
  const [data, setData] = useState<CourseStructureResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    const trimmed = courseId.trim()
    if (!enabled || trimmed.length < 2) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setError(null)

    void fetchCourseStructure(trimmed, controller.signal)
      .then((response) => {
        setData(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof CourseStructureApiError) {
          setError(`${err.status}: ${err.message}`)
        } else {
          setError(err instanceof Error ? err.message : 'Could not load course structure.')
        }
        setData(null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [courseId, enabled])

  useEffect(() => {
    const cleanup = load()
    return cleanup
  }, [load, refreshToken])

  return { data, loading, error, reload: load }
}
