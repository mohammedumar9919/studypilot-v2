import type {
  CourseMapEligibilityResponse,
  CourseMapOutlinePreview,
  CourseMapPromoteResponse,
  CourseMapRebuildResponse,
} from '../types'
import { authFetch } from './authFetch'

export class CourseMapApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'CourseMapApiError'
    this.status = status
  }
}

const PAGE_STUB_UNIT_TITLE = / — pages \d+[–-]\d+/i

const PROMOTE_EXTRACTION_FAILURE_MESSAGE =
  "Couldn't read unit structure from your syllabus PDF. Try Upload outline (JSON) or a clearer syllabus file."

async function parseCourseMapError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new CourseMapApiError(detail, response.status)
}

export async function fetchCourseMapEligibility(
  courseId: string,
  signal?: AbortSignal,
): Promise<CourseMapEligibilityResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/course-map-eligibility`, { signal })

  if (!response.ok) {
    return parseCourseMapError(response)
  }

  return (await response.json()) as CourseMapEligibilityResponse
}

export async function promoteCourseMap(courseId: string): Promise<CourseMapPromoteResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/course-map/promote`, {
    method: 'POST',
  })

  if (!response.ok) {
    return parseCourseMapError(response)
  }

  return (await response.json()) as CourseMapPromoteResponse
}

export async function rebuildCourseMapOutline(
  courseId: string,
): Promise<CourseMapRebuildResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/course-map/rebuild-outline`, {
    method: 'POST',
  })

  if (!response.ok) {
    return parseCourseMapError(response)
  }

  return (await response.json()) as CourseMapRebuildResponse
}

export function looksLikePageStubUnitTitle(title: string): boolean {
  return PAGE_STUB_UNIT_TITLE.test(title)
}

export function isOutlinePreviewNotReady(
  preview: CourseMapOutlinePreview | null | undefined,
): boolean {
  if (!preview) return false
  if (preview.outline_source === 'auto_stub') return true
  return preview.unit_titles.some(looksLikePageStubUnitTitle)
}

export function formatCourseMapPreviewLines(preview: CourseMapOutlinePreview): {
  visibleTitles: string[]
  remainingCount: number
} {
  const visibleTitles = preview.unit_titles.slice(0, 3)
  const remainingCount = Math.max(0, preview.unit_count - visibleTitles.length)
  return { visibleTitles, remainingCount }
}

export function courseMapIneligibilityMessage(
  reason: CourseMapEligibilityResponse['reason'],
): string {
  switch (reason) {
    case 'no_syllabus_document':
      return 'Upload a syllabus PDF with Syllabus / course map intent first.'
    case 'no_outline':
    case 'outline_quality_not_high':
      return 'Upload a syllabus or improve outline quality first.'
    case 'already_mapped':
      return 'This course already uses Course Map.'
    default:
      return 'Course Map is not available for this course yet.'
  }
}

export function formatCourseMapPromoteError(err: unknown): string {
  if (err instanceof CourseMapApiError) {
    if (err.status === 422) {
      return PROMOTE_EXTRACTION_FAILURE_MESSAGE
    }
    return `${err.status}: ${err.message}`
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Could not promote to Course Map'
}

export function formatCourseMapRebuildError(err: unknown): string {
  if (err instanceof CourseMapApiError) {
    if (err.status === 422) {
      return PROMOTE_EXTRACTION_FAILURE_MESSAGE
    }
    return `${err.status}: ${err.message}`
  }
  if (err instanceof Error) {
    return err.message
  }
  return 'Could not extract outline from syllabus'
}

export function isCourseMapPromoteExtractionFailure(message: string | null): boolean {
  return message === PROMOTE_EXTRACTION_FAILURE_MESSAGE
}
