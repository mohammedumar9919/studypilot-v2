import type { QueryPreset, QueryResponse } from '../types'
import { isExamPreset } from '../constants/queryPresets'
import { SourcesList } from './SourcesList'

interface AnswerPanelProps {
  result: QueryResponse
  queryPreset?: QueryPreset
  examIndexReady?: boolean | null
  debugEnabled?: boolean
  isStreaming?: boolean
}

function formatRefusalReason(reason: string | null | undefined): string | null {
  if (!reason) return null
  if (reason === 'empty_corpus') return 'empty_corpus — no candidates retrieved before rerank'
  if (reason === 'below_threshold') return 'below_threshold — top rerank score below confidence gate'
  return reason
}

export function AnswerPanel({
  result,
  queryPreset = 'study',
  examIndexReady = null,
  debugEnabled = false,
  isStreaming = false,
}: AnswerPanelProps) {
  if (result.status === 'not_in_materials') {
    const refusalReason = result.retrieval_debug?.refusal_reason
    const topScore = result.retrieval_debug?.top_rerank_score
    const refusalDebug =
      debugEnabled && (refusalReason != null || topScore != null) ? (
        <p className="muted exam-refusal-debug" role="status">
          {formatRefusalReason(refusalReason)}
          {topScore != null && ` · top rerank: ${topScore.toFixed(3)}`}
        </p>
      ) : null

    if (isExamPreset(queryPreset)) {
      if (examIndexReady === false) {
        return (
          <section className="panel answer-panel glass-panel refusal reveal-block exam-refusal-panel">
            <h2>Past papers not indexed yet</h2>
            <p>Exam mode searches ingested past papers only — none are ready for this course yet.</p>
            <ul className="exam-refusal-steps">
              <li>
                Upload a PDF using the <strong>Past paper</strong> document type above
              </li>
              <li>Wait for indexing to finish, then try again</li>
              <li>Check the exam topic frequency panel for indexed papers</li>
            </ul>
            {refusalDebug}
          </section>
        )
      }

      if (examIndexReady === true) {
        return (
          <section className="panel answer-panel glass-panel refusal reveal-block exam-refusal-panel">
            <h2>No past-paper match</h2>
            <p>
              No past-paper match for this question. Try rephrasing, pick a topic from the heatmap,
              or use an example chip.
            </p>
            {refusalDebug}
          </section>
        )
      }

      return (
        <section className="panel answer-panel glass-panel refusal reveal-block exam-refusal-panel">
          <h2>No past-paper match</h2>
          <p>
            Exam mode searches ingested past papers only — no relevant exam content was found for
            this question.
          </p>
          {refusalDebug}
        </section>
      )
    }

    return (
      <section className="panel answer-panel glass-panel refusal reveal-block">
        <h2>Not in materials</h2>
        <p>
          The confidence gate did not find relevant content in the course corpus for this
          question.
        </p>
        {refusalDebug}
      </section>
    )
  }

  const answerText = result.answer ?? ''
  const showSources = result.sources.length > 0
  const showAnswerSection = isStreaming || answerText.length > 0

  return (
    <section className="panel answer-panel glass-panel reveal-block">
      {showSources && (
        <div className="sources-reveal stagger-1">
          <h2>Sources</h2>
          <SourcesList sources={result.sources} debugChunks={result.retrieval_debug?.chunks} />
        </div>
      )}

      {showAnswerSection && (
        <div className={`answer-block stagger-2 ${isStreaming ? 'is-streaming' : ''}`}>
          {showSources ? <h3>Answer</h3> : <h2>Answer</h2>}
          <div className={`answer-text ${isStreaming ? 'answer-streaming' : ''}`}>
            {answerText}
            {isStreaming && <span className="answer-cursor" aria-hidden="true" />}
          </div>
          {isStreaming && answerText.length === 0 && (
            <p className="muted answer-streaming-hint">Writing answer from your sources…</p>
          )}
        </div>
      )}
    </section>
  )
}
