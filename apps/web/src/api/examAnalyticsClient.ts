import { authFetch } from './authFetch'

export type ExamAnalyticsSort = 'weightage_desc' | 'count_desc' | 'label_asc'

export type ExamAnalyticsConcept = {
  concept_id: string
  label: string
  aliases: string[]
  is_unclassified: boolean
  question_count: number
  unique_question_count: number
  marks_total: number
  weightage_pct: number
  count_pct: number
  paper_reach: number
  recurrence_rate: number
  avg_marks: number
  long_count: number
  short_count: number
  last_seen_paper: string | null
  trend_slope: number | null
  rank: number
}

export type ExamAnalyticsNodeMetrics = {
  question_count: number
  unique_question_count: number
  marks_total: number
  weightage_pct: number
  count_pct: number
  long_count: number
  short_count: number
  paper_reach: number
  recurrence_rate: number
  concept_count: number
  mapped_concept_ids: string[]
}

export type ExamAnalyticsSubtopic = ExamAnalyticsNodeMetrics & {
  subtopic_id: string
  title: string
}

export type ExamAnalyticsPart = ExamAnalyticsNodeMetrics & {
  part_id: string
  title: string
  subtopics: ExamAnalyticsSubtopic[]
}

export type ExamAnalyticsUnit = ExamAnalyticsNodeMetrics & {
  unit_id: string
  title: string
  parts?: ExamAnalyticsPart[]
  subtopics?: ExamAnalyticsSubtopic[]
}

export type ExamAnalyticsUnmappedConcept = {
  concept_id: string
  label: string
}

export type ExamAnalyticsSummary = {
  question_count: number
  concept_count: number
  classified_concept_count: number
  unclassified_only_questions: number
  unclassified_pct: number
  total_marks: number
  distinct_papers: number
  long_question_threshold_marks: number
}

export type ExamAnalyticsResponse = {
  course_id: string
  tier: 1 | 2 | 3
  analytics_ready: boolean
  summary: ExamAnalyticsSummary
  concepts: ExamAnalyticsConcept[]
  pagination: { limit: number; offset: number; total: number }
  structure?: {
    structure_mode: string
    units: ExamAnalyticsUnit[]
  }
  unmapped_concepts?: ExamAnalyticsUnmappedConcept[]
}

export class ExamAnalyticsApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ExamAnalyticsApiError'
    this.status = status
  }
}

export async function fetchExamAnalytics(
  courseId: string,
  options?: {
    limit?: number
    offset?: number
    sort?: ExamAnalyticsSort
    includeStructure?: 'auto' | 'true' | 'false'
    includeUnclassified?: boolean
    signal?: AbortSignal
  },
): Promise<ExamAnalyticsResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const params = new URLSearchParams()
  params.set('limit', String(options?.limit ?? 50))
  params.set('offset', String(options?.offset ?? 0))
  params.set('sort', options?.sort ?? 'weightage_desc')
  params.set('include_structure', options?.includeStructure ?? 'auto')
  if (options?.includeUnclassified) {
    params.set('include_unclassified', 'true')
  }

  const response = await authFetch(
    `/api/v1/courses/${encoded}/exam/analytics?${params.toString()}`,
    { signal: options?.signal },
  )

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new ExamAnalyticsApiError(detail, response.status)
  }

  return (await response.json()) as ExamAnalyticsResponse
}
