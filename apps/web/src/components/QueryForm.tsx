import type { FormEvent } from 'react'

import { EXAMPLE_QUESTIONS } from '../constants/exampleQuestions'

interface QueryFormProps {
  courseId: string
  question: string
  debugEnabled: boolean
  loading: boolean
  onCourseIdChange: (value: string) => void
  onQuestionChange: (value: string) => void
  onDebugChange: (value: boolean) => void
  onSubmit: () => void
}

export function QueryForm({
  courseId,
  question,
  debugEnabled,
  loading,
  onCourseIdChange,
  onQuestionChange,
  onDebugChange,
  onSubmit,
}: QueryFormProps) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!loading && question.trim()) onSubmit()
  }

  return (
    <form className="query-form panel" onSubmit={handleSubmit}>
      <h2>Ask a question</h2>
      <p className="panel-intro">Ask your course notes — answers include page citations.</p>

      <label className="field">
        <span>Course ID</span>
        <input
          type="text"
          value={courseId}
          onChange={(event) => onCourseIdChange(event.target.value)}
          disabled={loading}
          autoComplete="off"
        />
      </label>

      <label className="field">
        <span>Question</span>
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          rows={4}
          disabled={loading}
          placeholder="e.g. What is a lexeme?"
          required
        />
      </label>

      <div className="example-questions">
        <span className="example-questions-label">Try an example</span>
        <div className="example-question-chips">
          {EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example}
              type="button"
              className="example-chip"
              disabled={loading}
              onClick={() => onQuestionChange(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      <label className="checkbox-field debug-toggle">
        <input
          type="checkbox"
          checked={debugEnabled}
          onChange={(event) => onDebugChange(event.target.checked)}
          disabled={loading}
        />
        <span>Developer mode (rerank scores + retrieval debug)</span>
      </label>

      <button type="submit" className="submit-btn" disabled={loading || !question.trim()}>
        {loading ? (
          <>
            <span className="spinner spinner-inline" aria-hidden="true" />
            Working…
          </>
        ) : (
          'Ask'
        )}
      </button>
    </form>
  )
}
