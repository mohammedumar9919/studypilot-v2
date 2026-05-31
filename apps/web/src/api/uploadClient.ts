import type { DocumentKind, DocumentUploadResponse } from '../types'

const UPLOAD_TIMEOUT_MS = 120_000

export class UploadApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'UploadApiError'
    this.status = status
  }
}

export async function postDocumentUpload(
  courseId: string,
  file: File,
  docKind: DocumentKind,
  signal?: AbortSignal,
): Promise<DocumentUploadResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_kind', docKind)

  const timeoutController = new AbortController()
  const timeoutId = window.setTimeout(() => timeoutController.abort(), UPLOAD_TIMEOUT_MS)

  const onAbort = () => timeoutController.abort()
  signal?.addEventListener('abort', onAbort)

  try {
    const response = await fetch(`/api/v1/courses/${encoded}/documents`, {
      method: 'POST',
      body: formData,
      signal: timeoutController.signal,
    })

    if (!response.ok) {
      let detail = response.statusText
      try {
        const payload = (await response.json()) as { detail?: string }
        if (payload.detail) detail = payload.detail
      } catch {
        // ignore parse errors
      }
      throw new UploadApiError(detail, response.status)
    }

    return (await response.json()) as DocumentUploadResponse
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (signal?.aborted) throw err
      throw new UploadApiError('Upload timed out after 2 minutes. Try again or use a smaller PDF.', 408)
    }
    throw err
  } finally {
    window.clearTimeout(timeoutId)
    signal?.removeEventListener('abort', onAbort)
  }
}
