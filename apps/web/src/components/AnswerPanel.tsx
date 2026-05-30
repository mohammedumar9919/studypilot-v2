import type { QueryResponse } from '../types'
import { SourcesList } from './SourcesList'

interface AnswerPanelProps {
  result: QueryResponse
  isStreaming?: boolean
}

export function AnswerPanel({ result, isStreaming = false }: AnswerPanelProps) {
  if (result.status === 'not_in_materials') {
    return (
      <section className="panel answer-panel refusal">
        <h2>Not in materials</h2>
        <p>
          The confidence gate did not find relevant content in the course corpus for this
          question.
        </p>
      </section>
    )
  }

  const answerText = result.answer ?? ''
  const showSources = result.sources.length > 0
  const showAnswerSection = isStreaming || answerText.length > 0

  return (
    <section className="panel answer-panel">
      {showSources && (
        <>
          <h2>Sources</h2>
          <SourcesList sources={result.sources} debugChunks={result.retrieval_debug?.chunks} />
        </>
      )}

      {showAnswerSection && (
        <>
          {showSources ? <h3>Answer</h3> : <h2>Answer</h2>}
          <div className={`answer-text ${isStreaming ? 'answer-streaming' : ''}`}>
            {answerText}
            {isStreaming && <span className="answer-cursor" aria-hidden="true" />}
          </div>
          {isStreaming && answerText.length === 0 && (
            <p className="muted answer-streaming-hint">Writing answer from your sources…</p>
          )}
        </>
      )}
    </section>
  )
}
