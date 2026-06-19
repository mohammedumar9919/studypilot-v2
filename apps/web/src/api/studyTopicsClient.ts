import type {
  DocumentTopicAssignmentResponse,
  StructureMode,
  StructureModeResponse,
  StudyTopic,
  StudyTopicsBulkResponse,
  StudyTopicsResponse,
} from '../types'
import { authFetch } from './authFetch'

export class StudyTopicsApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'StudyTopicsApiError'
    this.status = status
  }
}

async function parseStudyTopicsError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new StudyTopicsApiError(detail, response.status)
}

export async function fetchStudyTopics(
  courseId: string,
  signal?: AbortSignal,
): Promise<StudyTopicsResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/study-topics`, { signal })

  if (!response.ok) {
    return parseStudyTopicsError(response)
  }

  return (await response.json()) as StudyTopicsResponse
}

export async function createStudyTopic(
  courseId: string,
  title: string,
  sortOrder = 0,
): Promise<StudyTopic> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/study-topics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, sort_order: sortOrder }),
  })

  if (!response.ok) {
    return parseStudyTopicsError(response)
  }

  return (await response.json()) as StudyTopic
}

export async function bulkCreateStudyTopics(
  courseId: string,
  titles: string[],
): Promise<StudyTopicsBulkResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/study-topics/bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ titles }),
  })

  if (!response.ok) {
    return parseStudyTopicsError(response)
  }

  return (await response.json()) as StudyTopicsBulkResponse
}

export async function patchStructureMode(
  courseId: string,
  structureMode: Extract<StructureMode, 'corpus' | 'organized'>,
): Promise<StructureModeResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/structure-mode`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ structure_mode: structureMode }),
  })

  if (!response.ok) {
    return parseStudyTopicsError(response)
  }

  return (await response.json()) as StructureModeResponse
}

export async function patchDocumentTopic(
  documentId: string,
  topicId: string | null,
): Promise<DocumentTopicAssignmentResponse> {
  const response = await authFetch(`/api/v1/documents/${encodeURIComponent(documentId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id: topicId }),
  })

  if (!response.ok) {
    return parseStudyTopicsError(response)
  }

  return (await response.json()) as DocumentTopicAssignmentResponse
}
