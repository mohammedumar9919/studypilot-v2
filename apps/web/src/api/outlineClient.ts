import type { OutlineResponse, OutlineUploadPayload } from '../types'
import { authFetch } from './authFetch'

export class OutlineApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'OutlineApiError'
    this.status = status
  }
}

async function parseOutlineError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new OutlineApiError(detail, response.status)
}

export async function fetchCourseOutline(
  courseId: string,
  signal?: AbortSignal,
): Promise<OutlineResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/outline`, { signal })

  if (!response.ok) {
    return parseOutlineError(response)
  }

  return (await response.json()) as OutlineResponse
}

export async function postCourseOutline(
  courseId: string,
  body: OutlineUploadPayload,
  signal?: AbortSignal,
): Promise<OutlineResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/outline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    return parseOutlineError(response)
  }

  return (await response.json()) as OutlineResponse
}

export async function rebuildCourseOutline(
  courseId: string,
  signal?: AbortSignal,
): Promise<OutlineResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/outline/rebuild`, {
    method: 'POST',
    signal,
  })

  if (!response.ok) {
    return parseOutlineError(response)
  }

  return (await response.json()) as OutlineResponse
}
