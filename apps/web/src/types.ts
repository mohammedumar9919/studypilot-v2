export interface QueryRequest {
  course_id: string
  question: string
  preset: 'study'
  debug: boolean
}

export interface Source {
  document_id: string
  filename: string
  page: number
  excerpt: string
}

export interface RetrievalDebugChunk {
  chunk_id: string
  document_id: string
  filename: string
  page: number
  rerank_score?: number | null
  /**
   * Outline metadata stamped on chunks (may be absent depending on ingest/version).
   * UI must treat these as optional.
   */
  unit?: string | null
  section_title?: string | null
  toc_path?: string | null
  /**
   * Optional short text for inspection (field name varies by backend version).
   * We keep it loose for UI-only compatibility.
   */
  excerpt?: string | null
  snippet?: string | null
  text?: string | null
}

export interface RetrievalDebug {
  chunk_count: number
  pages: number[]
  filenames: string[]
  rerank_scores: number[]
  chunks: RetrievalDebugChunk[]
}

export interface QueryResponse {
  status: 'ok' | 'not_in_materials'
  answer: string | null
  sources: Source[]
  rerank_scores: number[]
  retrieval_debug: RetrievalDebug | null
}

export interface StreamRetrievalCompletePayload {
  sources: Source[]
  chunk_count: number
  rerank_scores: number[]
  retrieval_debug: RetrievalDebug | null
}

export interface StreamTokenPayload {
  delta: string
}

export interface StreamErrorPayload {
  detail: string
  status_code?: number
}

export interface StreamEventHandlers {
  onRetrievalComplete?: (payload: StreamRetrievalCompletePayload) => void
  onToken?: (payload: StreamTokenPayload) => void
  onDone?: (payload: QueryResponse) => void
  onError?: (payload: StreamErrorPayload) => void
}

/** Stages for progress UX; extend when API adds streaming. */
export type QueryStage = 'idle' | 'retrieving' | 'generating' | 'done' | 'error'

export interface GoldenMissHint {
  id: string
  question: string
  expectedDoc: string
  expectedPages: number[]
  unit: string
}

export interface TopicFrequencySection {
  section_title: string
  count: number
}

export interface TopicFrequencyUnit {
  unit: string
  title: string
  count: number
  sections: TopicFrequencySection[]
}

export interface TopicFrequencySourceDocument {
  filename: string
  readable_pages: number[]
  chunk_count: number
}

export interface TopicFrequencyResponse {
  course_id: string
  total_questions_estimated: number
  coverage_note: string
  units: TopicFrequencyUnit[]
  source_documents: TopicFrequencySourceDocument[]
}

export interface OutlinePageRange {
  title: string
  page_start: number
  page_end: number
}

export interface OutlineSection {
  title: string
  page_start: number
  page_end: number
}

export interface OutlineUnit {
  id: string
  title: string
  page_start: number
  page_end: number
  sections: OutlineSection[]
}

export interface OutlineResponse {
  course_id: string
  document: string
  page_index_base: number
  page_count: number
  front_matter: OutlinePageRange
  units: OutlineUnit[]
}

export type DocumentKind = 'notes' | 'textbook' | 'syllabus' | 'past_paper'

export interface DocumentUploadExtractionQuality {
  nonempty_pages?: number
  total_pages?: number
  outline?: { unit_count?: number }
}

export interface DocumentUploadResponse {
  document_id: string
  course_id: string
  filename: string
  doc_kind: DocumentKind
  status: 'ready' | 'failed' | 'pending' | 'processing'
  page_count: number
  extraction_quality: DocumentUploadExtractionQuality | null
}

export type UploadPanelPhase = 'idle' | 'indexing' | 'success' | 'error'
