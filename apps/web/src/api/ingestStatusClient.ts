import type { DocumentKind, DocumentUploadResponse, IngestStatusResponse } from '../types'
import { authFetch } from './authFetch'
import { uploadTimeoutMinutes } from './uploadClient'

export class IngestStatusApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'IngestStatusApiError'
    this.status = status
  }
}

export class IngestPollError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'IngestPollError'
  }
}

const POLL_INTERVAL_MS = 2000

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      window.clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort)
  })
}

async function parseApiError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new IngestStatusApiError(detail, response.status)
}

export async function fetchIngestStatus(
  documentId: string,
  signal?: AbortSignal,
): Promise<IngestStatusResponse> {
  const response = await authFetch(
    `/api/v1/documents/${encodeURIComponent(documentId)}/ingest-status`,
    { signal },
  )
  if (!response.ok) {
    return parseApiError(response)
  }
  return (await response.json()) as IngestStatusResponse
}

function pollTimeoutMs(docKind: DocumentKind): number {
  return uploadTimeoutMinutes(docKind) * 60_000
}

function isTerminalFailure(status: IngestStatusResponse): boolean {
  const docStatus = status.document_status ?? status.status
  return docStatus === 'failed' || status.status === 'failed'
}

function isTerminalSuccess(status: IngestStatusResponse): boolean {
  const docStatus = status.document_status ?? status.status
  return docStatus === 'ready'
}

export async function pollIngestStatusUntilDone(
  documentId: string,
  docKind: DocumentKind,
  options: {
    signal?: AbortSignal
    onUpdate?: (status: IngestStatusResponse) => void
  } = {},
): Promise<IngestStatusResponse> {
  const maxWaitMs = pollTimeoutMs(docKind)
  const started = Date.now()

  while (true) {
    if (options.signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }

    const status = await fetchIngestStatus(documentId, options.signal)
    options.onUpdate?.(status)

    if (isTerminalSuccess(status)) {
      return status
    }
    if (isTerminalFailure(status)) {
      throw new IngestPollError(status.error ?? 'Ingest failed')
    }

    if (Date.now() - started > maxWaitMs) {
      throw new IngestPollError(
        `Indexing timed out after ${uploadTimeoutMinutes(docKind)} minutes. Keep the worker running or retry.`,
      )
    }

    await sleep(POLL_INTERVAL_MS, options.signal)
  }
}

interface CourseDocumentRow {
  document_id: string
  filename: string
  page_count: number | null
  status: string
  doc_kind: DocumentKind
}

export async function enrichUploadAfterIngest(
  upload: DocumentUploadResponse,
  signal?: AbortSignal,
): Promise<DocumentUploadResponse> {
  const encoded = encodeURIComponent(upload.course_id.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/documents`, { signal })
  if (!response.ok) {
    return { ...upload, status: 'ready' }
  }

  const payload = (await response.json()) as { documents?: CourseDocumentRow[] }
  const match = payload.documents?.find((row) => row.document_id === upload.document_id)
  if (!match) {
    return { ...upload, status: 'ready' }
  }

  return {
    ...upload,
    status: 'ready',
    page_count: match.page_count ?? upload.page_count,
    filename: match.filename || upload.filename,
    doc_kind: match.doc_kind ?? upload.doc_kind,
  }
}

export function isAsyncQueuedUpload(response: DocumentUploadResponse): boolean {
  return response.status === 'queued' || Boolean(response.job_id)
}
