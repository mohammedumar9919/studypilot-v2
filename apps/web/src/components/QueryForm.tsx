import { useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'

import { EXAMPLE_QUESTIONS } from '../constants/exampleQuestions'
import {
  DEFAULT_EXAM_EXAMPLE_QUESTIONS,
  getQueryPresetOption,
  isExamPreset,
  QUERY_PRESET_OPTIONS,
} from '../constants/queryPresets'
import type { QueryPreset } from '../types'

interface QueryFormProps {
  courseId: string
  question: string
  preset: QueryPreset
  debugEnabled: boolean
  loading: boolean
  examIndexReady?: boolean | null
  examTopicChips?: string[]
  submitBlocked?: boolean
  submitBlockedMessage?: string | null
  onCourseIdCommit: (value: string) => void
  onQuestionChange: (value: string) => void
  onPresetChange: (value: QueryPreset) => void
  onDebugChange: (value: boolean) => void
  onSubmit: () => void
}

export function QueryForm({
  courseId,
  question,
  preset,
  debugEnabled,
  loading,
  examIndexReady = null,
  examTopicChips,
  submitBlocked = false,
  submitBlockedMessage = null,
  onCourseIdCommit,
  onQuestionChange,
  onPresetChange,
  onDebugChange,
  onSubmit,
}: QueryFormProps) {
  const [draftCourseId, setDraftCourseId] = useState(courseId)
  const presetOption = getQueryPresetOption(preset)

  const exampleQuestions = useMemo(() => {
    if (!isExamPreset(preset)) return [...EXAMPLE_QUESTIONS]
    if (examTopicChips && examTopicChips.length > 0) return examTopicChips
    return [...DEFAULT_EXAM_EXAMPLE_QUESTIONS]
  }, [preset, examTopicChips])

  const showExamUploadHint = isExamPreset(preset) && examIndexReady === false

  useEffect(() => {
    setDraftCourseId(courseId)
  }, [courseId])

  const commitCourseId = () => {
    const trimmed = draftCourseId.trim()
    if (trimmed !== courseId.trim()) {
      onCourseIdCommit(trimmed)
    }
  }

  const handleCourseKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      commitCourseId()
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (debugEnabled) commitCourseId()
    if (!loading && !submitBlocked && question.trim()) onSubmit()
  }

  const askDisabled = loading || !question.trim() || submitBlocked

  return (
    <form className="query-form panel" onSubmit={handleSubmit}>
      <h2>Ask a question</h2>

      <div className="preset-tabs" role="tablist" aria-label="Study mode">
        {QUERY_PRESET_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={preset === option.value}
            className={['preset-tab', preset === option.value ? 'is-active' : '']
              .filter(Boolean)
              .join(' ')}
            disabled={loading}
            onClick={() => onPresetChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <p className="panel-intro">{presetOption.hint}</p>

      {showExamUploadHint && (
        <div className="exam-preset-notice" role="status">
          <p>
            Past papers are not indexed yet. Upload a PDF and choose <strong>Past paper</strong> as
            the document type to practice exam questions.
          </p>
        </div>
      )}

      {debugEnabled ? (
        <label className="field">
          <span>Course ID</span>
          <input
            type="text"
            value={draftCourseId}
            onChange={(event) => setDraftCourseId(event.target.value)}
            onBlur={commitCourseId}
            onKeyDown={handleCourseKeyDown}
            disabled={loading}
            autoComplete="off"
          />
        </label>
      ) : (
        <p className="studying-pill" role="status">
          Studying: <strong>{courseId.trim() || '—'}</strong>
        </p>
      )}

      <label className="field">
        <span>Question</span>
        <textarea
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          rows={4}
          disabled={loading}
          placeholder={
            isExamPreset(preset)
              ? 'e.g. Questions on lexemes and tokens'
              : 'e.g. What is a lexeme?'
          }
          required
        />
      </label>

      <div className="example-questions">
        <span className="example-questions-label">Try an example</span>
        <div className="example-question-chips">
          {exampleQuestions.map((example) => (
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

      {submitBlocked && submitBlockedMessage && (
        <p className="query-validation-notice" role="status">
          {submitBlockedMessage}
        </p>
      )}

      <button type="submit" className="submit-btn" disabled={askDisabled}>
        {loading ? (
          <>
            <span className="spinner spinner-inline" aria-hidden="true" />
            Working…
          </>
        ) : (
          <>
            {presetOption.submitLabel}
            <span className="submit-arrow" aria-hidden="true">
              →
            </span>
          </>
        )}
      </button>
    </form>
  )
}
