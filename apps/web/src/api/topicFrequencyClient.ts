import type { TopicFrequencyResponse } from '../types'
import { authFetch } from './authFetch'

export class TopicFrequencyApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'TopicFrequencyApiError'
    this.status = status
  }
}

export async function fetchTopicFrequency(
  courseId: string,
  options?: { sectionDetail?: boolean; documentIds?: string[]; signal?: AbortSignal },
): Promise<TopicFrequencyResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const params = new URLSearchParams()
  if (options?.sectionDetail) params.set('detail', 'sections')
  for (const documentId of options?.documentIds ?? []) {
    params.append('document_ids', documentId)
  }
  const query = params.toString() ? `?${params.toString()}` : ''
  const response = await authFetch(`/api/v1/courses/${encoded}/exam/topic-frequency${query}`, {
    signal: options?.signal,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new TopicFrequencyApiError(detail, response.status)
  }

  return (await response.json()) as TopicFrequencyResponse
}
