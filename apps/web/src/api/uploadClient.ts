import type { DocumentKind, DocumentUploadResponse, UploadIntent } from '../types'
import { authFetch } from './authFetch'

/** Sync ingest on localhost — large PDFs + OCR exceed 2 min (SP-017.1 hotfix). */
const UPLOAD_TIMEOUT_MS: Record<DocumentKind, number> = {
  notes: 10 * 60 * 1000,
  textbook: 10 * 60 * 1000,
  syllabus: 10 * 60 * 1000,
  past_paper: 30 * 60 * 1000,
}

export function uploadTimeoutMinutes(docKind: DocumentKind): number {
  return UPLOAD_TIMEOUT_MS[docKind] / 60_000
}

function uploadTimeoutMessage(docKind: DocumentKind): string {
  const minutes = uploadTimeoutMinutes(docKind)
  return `Upload timed out after ${minutes} minutes. Large PDFs and past papers can take longer — try CLI ingest or wait for background indexing (SP-013).`
}

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
  uploadIntent: UploadIntent,
  signal?: AbortSignal,
): Promise<DocumentUploadResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_kind', docKind)
  formData.append('upload_intent', uploadIntent)

  const timeoutMs = UPLOAD_TIMEOUT_MS[docKind]
  const timeoutController = new AbortController()
  const timeoutId = window.setTimeout(() => timeoutController.abort(), timeoutMs)

  const onAbort = () => timeoutController.abort()
  signal?.addEventListener('abort', onAbort)

  try {
    const response = await authFetch(`/api/v1/courses/${encoded}/documents`, {
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
      throw new UploadApiError(uploadTimeoutMessage(docKind), 408)
    }
    throw err
  } finally {
    window.clearTimeout(timeoutId)
    signal?.removeEventListener('abort', onAbort)
  }
}
