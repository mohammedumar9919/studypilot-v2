export type QueryPreset = 'study' | 'summary' | 'flashcards' | 'exam'

export interface QueryRequest {
  course_id: string
  question: string
  preset: QueryPreset
  debug: boolean
  /** Corpus mode subset only — omit when all ready sources are selected. */
  source_ids?: string[]
  /** Organized mode subset only — omit when all topics are selected. */
  topic_ids?: string[]
  /** Structure scope — study presets only; mutually exclusive with source_ids/topic_ids. */
  unit_ids?: string[]
  part_ids?: string[]
  subtopic_ids?: string[]
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
  chunk_count?: number
  pages?: number[]
  filenames?: string[]
  rerank_scores?: number[]
  chunks?: RetrievalDebugChunk[]
  refusal_reason?: string | null
  top_rerank_score?: number | null
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
  sections?: TopicFrequencySection[]
}

export interface TopicFrequencySourceDocument {
  filename: string
  readable_pages: number[]
  chunk_count: number
}

export type ExamHeatmapSource = 'parsed' | 'seed' | 'keyword' | 'none'

export interface ExamStatusResponse {
  course_id: string
  documents_ready: boolean
  document_count: number
  readable_pages: number
  total_pages: number
  chunk_count: number
  embedded_chunk_count: number
  embeddings_ready: boolean
  parsed_questions: number
  has_pyq_seed: boolean
  exam_index_ready: boolean
  heatmap_available: boolean
  heatmap_source: ExamHeatmapSource
  question_count_source?: 'exam_questions' | 'none'
  readable_char_threshold: number
  source_documents: TopicFrequencySourceDocument[]
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

export type OutlineSource = 'fixture' | 'uploaded' | 'extracted' | 'auto_stub'

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

export type OutlineGranularity = 'chapter' | 'section' | 'page_stub'

export type OutlineQuality = 'high' | 'medium' | 'low'

export interface OutlineUploadPayload {
  document: string
  page_index_base: number
  page_count: number
  front_matter?: OutlinePageRange | null
  units: OutlineUnit[]
}

export interface OutlineResponse {
  course_id: string
  document: string
  page_index_base: number
  page_count: number
  outline_source?: OutlineSource
  outline_granularity?: OutlineGranularity
  outline_quality?: OutlineQuality
  front_matter: OutlinePageRange | null
  units: OutlineUnit[]
}

export type DocumentKind = 'notes' | 'textbook' | 'syllabus' | 'past_paper'

export type UploadIntent = 'quick' | 'topic' | 'past_paper' | 'syllabus'

export type StudyLayoutMode = 'corpus' | 'mapped'

export type StructureMode = 'corpus' | 'organized' | 'mapped'

export type StudyLayoutSourceStatus = 'ready' | 'processing'

export interface StudyLayoutSource {
  document_id: string
  filename: string
  page_count: number
  status: StudyLayoutSourceStatus
  doc_kind: DocumentKind
  topic_id?: string | null
}

export interface SidebarViews {
  sources: boolean
  /** @deprecated SP-053c — use course_structure for non-PPL flex sidebar */
  topics: boolean
  /** @deprecated SP-053c — PPL fixture only */
  course_map: boolean
  /** Unified units/parts/subtopics tab (non-PPL flex sidebar). */
  course_structure?: boolean
}

export type SidebarViewTab = 'sources' | 'topics' | 'course_map' | 'course_structure'

export interface CourseStructureSubtopic {
  id: string
  title: string
  sort_order: number
  document_ids: string[]
}

export interface CourseStructurePart {
  id: string
  title: string
  sort_order: number
  subtopics: CourseStructureSubtopic[]
  document_ids: string[]
}

export interface CourseStructureUnit {
  id: string
  title: string
  sort_order: number
  parts?: CourseStructurePart[]
  subtopics?: CourseStructureSubtopic[]
  document_ids: string[]
}

export interface CourseStructureResponse {
  course_id: string
  units: CourseStructureUnit[]
}

export interface StructurePreviewPart {
  title: string
  subtopics: string[]
}

export interface StructurePreviewUnit {
  title: string
  parts?: StructurePreviewPart[]
  subtopics?: string[]
}

export interface StructureImportPreviewResponse {
  preview: true
  units: StructurePreviewUnit[]
  parse_warning?: string | null
}

export interface StudyLayoutResponse {
  mode: StudyLayoutMode
  structure_mode?: StructureMode
  course_id: string
  sources: StudyLayoutSource[]
  sidebar_views?: SidebarViews
  outline_available?: boolean
  promotion_hint?: string | null
}

export interface StudyTopic {
  id: string
  course_id: string
  title: string
  sort_order: number
}

export interface StudyTopicsResponse {
  course_id: string
  topics: StudyTopic[]
}

export interface StudyTopicsBulkResponse {
  course_id: string
  structure_mode: StructureMode
  topics: StudyTopic[]
}

export interface StructureModeResponse {
  course_id: string
  structure_mode: StructureMode
  mode: StudyLayoutMode
}

export interface DocumentTopicAssignmentResponse {
  document_id: string
  course_id: string
  topic_id: string | null
}

export type CourseMapIneligibilityReason =
  | 'already_mapped'
  | 'no_syllabus_document'
  | 'no_outline'
  | 'outline_quality_not_high'
  | 'not_eligible'

export type OutlineQualityLevel = 'high' | 'medium' | 'low'

export interface CourseMapOutlinePreview {
  outline_source?: OutlineSource | null
  unit_count: number
  unit_titles: string[]
}

export interface CourseMapEligibilityResponse {
  eligible: boolean
  outline_quality: OutlineQualityLevel | null
  structure_mode: StructureMode
  reason: CourseMapIneligibilityReason | null
  syllabus_filename?: string | null
  outline_preview?: CourseMapOutlinePreview | null
}

export interface CourseMapPromoteOutlineSummary {
  unit_count: number
  unit_titles: string[]
  outline_quality?: OutlineQualityLevel | null
  outline_source?: OutlineSource | null
}

export interface CourseMapPromoteResponse {
  course_id: string
  structure_mode: StructureMode
  mode: StudyLayoutMode
  promoted: boolean
  outline_summary?: CourseMapPromoteOutlineSummary | null
}

export interface CourseMapRebuildResponse {
  course_id: string
  rebuilt: boolean
  outline_summary?: CourseMapPromoteOutlineSummary | null
}

export interface DocumentUploadExtractionQuality {
  nonempty_pages?: number
  total_pages?: number
  upload_intent?: UploadIntent
  outline?: { unit_count?: number }
}

export interface DocumentUploadResponse {
  document_id: string
  course_id: string
  filename: string
  doc_kind: DocumentKind
  status: 'ready' | 'failed' | 'pending' | 'processing' | 'queued'
  page_count: number | null
  upload_intent?: UploadIntent
  extraction_quality: DocumentUploadExtractionQuality | null
  job_id?: string | null
}

export interface IngestStatusResponse {
  document_id: string
  job_id: string | null
  status: string
  phase: string
  progress_pct: number | null
  error: string | null
  document_status: string | null
}

export type UploadPanelPhase = 'idle' | 'indexing' | 'success' | 'error'
