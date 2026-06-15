import type { ExamStatusResponse } from '../types'
import { authFetch } from './authFetch'

export class ExamStatusApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ExamStatusApiError'
    this.status = status
  }
}

export async function fetchExamStatus(
  courseId: string,
  signal?: AbortSignal,
): Promise<ExamStatusResponse> {
  const trimmed = courseId.trim()
  if (trimmed.length < 2) {
    throw new ExamStatusApiError('Course ID must be at least 2 characters.', 400)
  }

  const encoded = encodeURIComponent(trimmed)
  const response = await authFetch(`/api/v1/courses/${encoded}/exam/status`, { signal })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new ExamStatusApiError(detail, response.status)
  }

  return (await response.json()) as ExamStatusResponse
}
