import type { TopicFrequencyResponse } from '../types'

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
  signal?: AbortSignal,
): Promise<TopicFrequencyResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await fetch(`/api/v1/courses/${encoded}/exam/topic-frequency`, { signal })

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
