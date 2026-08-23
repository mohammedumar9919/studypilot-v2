import { authFetch } from './authFetch'

export type ExamAnswerSource = {
  document_id: string
  filename: string
  page: number
  excerpt: string
}

export type ExamAnswerCoverageDocument = {
  document_id: string
  filename: string
  status: 'hit' | 'miss'
  top_rerank_score?: number | null
}

export type ExamAnswerResponse = {
  course_id: string
  tier: number
  answers_available: boolean
  target_type: 'concept' | 'question'
  target_id: string
  query_text: string
  answer_length: 'short' | 'medium' | 'long'
  status: 'ok' | 'no_study_docs' | 'not_in_materials'
  answer: string | null
  refusal_reason?: string | null
  top_rerank_score?: number | null
  sources: ExamAnswerSource[]
  coverage: {
    documents: ExamAnswerCoverageDocument[]
    hit_count: number
    miss_count: number
  }
}

export type ExamAnswerRequest =
  | { concept_id: string; question_id?: never; structure_node_id?: string }
  | { question_id: string; concept_id?: never; structure_node_id?: string }

export class ExamAnswerApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ExamAnswerApiError'
    this.status = status
  }
}

export async function postExamAnswer(
  courseId: string,
  body: ExamAnswerRequest,
  options?: { signal?: AbortSignal },
): Promise<ExamAnswerResponse> {
  const encoded = encodeURIComponent(courseId.trim())
  const response = await authFetch(`/api/v1/courses/${encoded}/exam/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: options?.signal,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // ignore parse errors
    }
    throw new ExamAnswerApiError(detail, response.status)
  }

  return (await response.json()) as ExamAnswerResponse
}
