import type {
  CourseStructureResponse,
  StructureImportPreviewResponse,
  StructurePreviewUnit,
} from '../types'

export class CourseStructureApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'CourseStructureApiError'
    this.status = status
  }
}

async function parseCourseStructureError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new CourseStructureApiError(detail, response.status)
}

function coursePath(courseId: string): string {
  return `/api/v1/courses/${encodeURIComponent(courseId.trim())}/structure`
}

export async function fetchCourseStructure(
  courseId: string,
  signal?: AbortSignal,
): Promise<CourseStructureResponse> {
  const response = await fetch(coursePath(courseId), { signal })

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as CourseStructureResponse
}

export async function importStructurePaste(
  courseId: string,
  text: string,
): Promise<StructureImportPreviewResponse> {
  const response = await fetch(`${coursePath(courseId)}/import-paste`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as StructureImportPreviewResponse
}

export async function importStructureSyllabus(
  courseId: string,
  documentId?: string,
): Promise<StructureImportPreviewResponse> {
  const body = documentId ? { document_id: documentId } : {}
  const response = await fetch(`${coursePath(courseId)}/import-syllabus`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as StructureImportPreviewResponse
}

export async function confirmCourseStructure(
  courseId: string,
  units: StructurePreviewUnit[],
): Promise<CourseStructureResponse> {
  const response = await fetch(`${coursePath(courseId)}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ units }),
  })

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as CourseStructureResponse
}

export async function assignUnitDocuments(
  courseId: string,
  unitId: string,
  documentIds: string[],
): Promise<CourseStructureResponse> {
  const response = await fetch(
    `${coursePath(courseId)}/units/${encodeURIComponent(unitId)}/documents`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_ids: documentIds }),
    },
  )

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as CourseStructureResponse
}

export async function assignPartDocuments(
  courseId: string,
  partId: string,
  documentIds: string[],
): Promise<CourseStructureResponse> {
  const response = await fetch(
    `${coursePath(courseId)}/parts/${encodeURIComponent(partId)}/documents`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_ids: documentIds }),
    },
  )

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as CourseStructureResponse
}

export async function assignSubtopicDocuments(
  courseId: string,
  subtopicId: string,
  documentIds: string[],
): Promise<CourseStructureResponse> {
  const response = await fetch(
    `${coursePath(courseId)}/subtopics/${encodeURIComponent(subtopicId)}/documents`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_ids: documentIds }),
    },
  )

  if (!response.ok) {
    return parseCourseStructureError(response)
  }

  return (await response.json()) as CourseStructureResponse
}
