import type {
  QueryRequest,
  QueryResponse,
  StreamErrorPayload,
  StreamEventHandlers,
  StreamRetrievalCompletePayload,
  StreamTokenPayload,
} from '../types'
import { parseSseFrame, splitSseFrames } from '../utils/sseParser'
import { authFetch } from './authFetch'

const QUERY_ENDPOINT = '/api/v1/query'
const STREAM_ENDPOINT = '/api/v1/query/stream'

export class QueryApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'QueryApiError'
    this.status = status
  }
}

/**
 * Single POST query. Non-stream fallback when SSE is unavailable.
 */
export async function postStudyQuery(
  body: QueryRequest,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  const response = await authFetch(QUERY_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new QueryApiError(detail, response.status)
  }

  return (await response.json()) as QueryResponse
}

function dispatchStreamEvent(event: string, data: unknown, handlers: StreamEventHandlers): void {
  switch (event) {
    case 'retrieval_complete':
      handlers.onRetrievalComplete?.(data as StreamRetrievalCompletePayload)
      return
    case 'token':
      handlers.onToken?.(data as StreamTokenPayload)
      return
    case 'done':
      handlers.onDone?.(data as QueryResponse)
      return
    case 'error':
      handlers.onError?.(data as StreamErrorPayload)
      return
    default:
      return
  }
}

/**
 * SSE stream query — invokes handlers as frames arrive.
 */
export async function postStudyQueryStream(
  body: QueryRequest,
  handlers: StreamEventHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await authFetch(STREAM_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new QueryApiError(detail, response.status)
  }

  if (!response.body) {
    throw new Error('Stream response has no body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const { frames, remainder } = splitSseFrames(buffer)
      buffer = remainder

      for (const frame of frames) {
        const parsed = parseSseFrame(frame)
        dispatchStreamEvent(parsed.event, parsed.data, handlers)
      }
    }

    if (buffer.trim()) {
      const parsed = parseSseFrame(buffer.trim())
      dispatchStreamEvent(parsed.event, parsed.data, handlers)
    }
  } finally {
    reader.releaseLock()
  }
}
