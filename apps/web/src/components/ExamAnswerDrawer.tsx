import { useCallback, useEffect, useState } from 'react'

import {
  ExamAnswerApiError,
  type ExamAnswerResponse,
  postExamAnswer,
} from '../api/examAnswerClient'

type ExamAnswerDrawerProps = {
  courseId: string
  conceptId?: string
  questionId?: string
  structureNodeId?: string
  label?: string
  open: boolean
  onClose: () => void
}

export function ExamAnswerDrawer({
  courseId,
  conceptId,
  questionId,
  structureNodeId,
  label,
  open,
  onClose,
}: ExamAnswerDrawerProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ExamAnswerResponse | null>(null)

  const loadAnswer = useCallback(async () => {
    if (!open) return
    if (!conceptId && !questionId) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const body = conceptId
        ? {
            concept_id: conceptId,
            ...(structureNodeId ? { structure_node_id: structureNodeId } : {}),
          }
        : {
            question_id: questionId!,
            ...(structureNodeId ? { structure_node_id: structureNodeId } : {}),
          }
      const response = await postExamAnswer(courseId, body)
      setResult(response)
    } catch (err) {
      const message =
        err instanceof ExamAnswerApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Could not load answer'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [courseId, conceptId, questionId, structureNodeId, open])

  useEffect(() => {
    void loadAnswer()
  }, [loadAnswer])

  if (!open) return null

  const title = label ? `Answer: ${label}` : 'Answer from materials'

  return (
    <div className="exam-answer-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="exam-answer-drawer panel"
        role="dialog"
        aria-labelledby="exam-answer-drawer-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="exam-answer-drawer-header">
          <div>
            <h3 id="exam-answer-drawer-title">{title}</h3>
            <p className="muted panel-intro">Grounded in your notes, textbook, and syllabus only.</p>
          </div>
          <button type="button" className="text-btn" onClick={onClose}>
            Close
          </button>
        </header>

        {loading && (
          <div className="exam-answer-drawer-loading" role="status">
            <span className="spinner" aria-hidden="true" />
            Generating answer…
          </div>
        )}

        {!loading && error && (
          <div className="exam-answer-drawer-alert alert-error" role="alert">
            <p>{error}</p>
            <button type="button" className="text-btn" onClick={() => void loadAnswer()}>
              Retry
            </button>
          </div>
        )}

        {!loading && result && !result.answers_available && (
          <div className="exam-answer-drawer-empty" role="status">
            <p>
              <strong>Upload notes to unlock answers.</strong>
            </p>
            <p className="muted">
              This course has past papers but no indexed study materials yet. Add notes, textbook, or
              syllabus PDFs to get grounded answers.
            </p>
          </div>
        )}

        {!loading && result && result.answers_available && result.status === 'not_in_materials' && (
          <div className="exam-answer-drawer-empty" role="status">
            <p>Not found in your study materials.</p>
            <p className="muted">Try uploading more notes or broadening your course outline.</p>
          </div>
        )}

        {!loading && result?.answer && (
          <div className="exam-answer-drawer-body">
            <p className="exam-answer-text">{result.answer}</p>

            {result.sources.length > 0 && (
              <section className="exam-answer-sources">
                <h4>Sources</h4>
                <ul>
                  {result.sources.map((source) => (
                    <li key={`${source.document_id}-${source.page}`}>
                      <strong>{source.filename}</strong> (p. {source.page})
                      <p className="muted">{source.excerpt}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {result.coverage.documents.length > 0 && (
              <section className="exam-answer-coverage">
                <h4>PDF coverage</h4>
                <p className="muted">
                  {result.coverage.hit_count} hit · {result.coverage.miss_count} miss
                </p>
                <ul>
                  {result.coverage.documents.map((doc) => (
                    <li key={doc.document_id}>
                      <span>{doc.filename}</span>
                      <span className={doc.status === 'hit' ? 'coverage-hit' : 'coverage-miss'}>
                        {doc.status}
                        {doc.top_rerank_score != null ? ` (${doc.top_rerank_score})` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </aside>
    </div>
  )
}
