import type { SidebarViews, StructureMode, StudyLayoutMode, StudyLayoutResponse } from '../types'

export class StudyLayoutApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'StudyLayoutApiError'
    this.status = status
  }
}

/** SP-053c: non-PPL flex sidebar uses Sources + Course structure (not Topics/Course map). */
export function normalizeFlexSidebarViews(
  base: SidebarViews,
  isPpl: boolean,
): SidebarViews {
  if (isPpl) {
    return {
      sources: base.sources,
      topics: base.topics,
      course_map: base.course_map,
      course_structure: false,
    }
  }

  const showCourseStructure =
    base.course_structure ?? base.topics ?? base.course_map ?? true

  return {
    sources: base.sources,
    topics: false,
    course_map: false,
    course_structure: showCourseStructure,
  }
}

/** Local fallback when course is not in DB yet (404) — matches API mode rules. */
export function stubStudyLayout(courseId: string): StudyLayoutResponse {
  const trimmed = courseId.trim()
  const isPpl = trimmed.toUpperCase() === 'PPL'
  const structureMode: StructureMode = isPpl ? 'mapped' : 'corpus'
  const mode: StudyLayoutMode = structureMode === 'mapped' ? 'mapped' : 'corpus'
  return {
    mode,
    structure_mode: structureMode,
    course_id: trimmed,
    sources: [],
    sidebar_views: isPpl
      ? { sources: false, topics: false, course_map: true, course_structure: false }
      : { sources: false, topics: false, course_map: false, course_structure: true },
    outline_available: isPpl,
  }
}

async function parseStudyLayoutError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new StudyLayoutApiError(detail, response.status)
}

export async function fetchStudyLayout(
  courseId: string,
  signal?: AbortSignal,
): Promise<StudyLayoutResponse> {
  const trimmed = courseId.trim()
  if (trimmed.length < 2) {
    throw new StudyLayoutApiError('Course ID must be at least 2 characters.', 400)
  }

  const encoded = encodeURIComponent(trimmed)
  const response = await fetch(`/api/v1/courses/${encoded}/study-layout`, { signal })

  if (response.status === 404) {
    return stubStudyLayout(trimmed)
  }

  if (!response.ok) {
    return parseStudyLayoutError(response)
  }

  return (await response.json()) as StudyLayoutResponse
}
