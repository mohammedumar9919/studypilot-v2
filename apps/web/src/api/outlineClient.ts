import type { OutlineResponse } from '../types'

export class OutlineApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'OutlineApiError'
    this.status = status
  }
}

export async function fetchCourseOutline(
  courseId: string,
  signal?: AbortSignal,
): Promise<OutlineResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await fetch(`/api/v1/courses/${encoded}/outline`, { signal })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new OutlineApiError(detail, response.status)
  }

  return (await response.json()) as OutlineResponse
}
