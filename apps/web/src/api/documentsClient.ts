import { authFetch } from './authFetch'

export type PastPaperSource = {
  document_id: string
  filename: string
  page_count: number | null
  status: string
  doc_kind: string
  parsed_question_count: number
}

export class DocumentsApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'DocumentsApiError'
    this.status = status
  }
}

const DELETE_TIMEOUT_MS = 20_000

export async function fetchPastPaperSources(
  courseId: string,
  options?: { signal?: AbortSignal },
): Promise<PastPaperSource[]> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/exam/past-paper-sources`, {
    signal: options?.signal,
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore
    }
    throw new DocumentsApiError(detail, response.status)
  }
  const payload = (await response.json()) as { sources: PastPaperSource[] }
  return payload.sources
}

export async function deleteCourseDocument(
  courseId: string,
  documentId: string,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const encodedCourse = encodeURIComponent(courseId.trim())
  const encodedDoc = encodeURIComponent(documentId.trim())
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), DELETE_TIMEOUT_MS)

  const signal = options?.signal
  if (signal) {
    if (signal.aborted) controller.abort()
    else signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  try {
    const response = await authFetch(
      `/api/v1/courses/${encodedCourse}/documents/${encodedDoc}`,
      {
        method: 'DELETE',
        signal: controller.signal,
      },
    )
    if (!response.ok) {
      let detail = response.statusText
      try {
        const payload = (await response.json()) as { detail?: string }
        if (payload.detail) detail = payload.detail
      } catch {
        // ignore
      }
      throw new DocumentsApiError(detail, response.status)
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new DocumentsApiError('Delete timed out — try restarting the API and retry.', 408)
    }
    throw err
  } finally {
    window.clearTimeout(timeout)
  }
}
