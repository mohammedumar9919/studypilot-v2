import { useMemo } from 'react'
import type { CSSProperties } from 'react'

import { useTopicFrequency } from '../hooks/useTopicFrequency'

interface TopicFrequencyPanelProps {
  courseId: string
  refreshToken?: number
}

function isPartialCoverage(note: string): boolean {
  return /partial/i.test(note)
}

export function TopicFrequencyPanel({ courseId, refreshToken = 0 }: TopicFrequencyPanelProps) {
  const { data, loading, error, notFound, reload } = useTopicFrequency(courseId, refreshToken)

  const maxUnitCount = useMemo(() => {
    if (!data?.units.length) return 1
    return Math.max(...data.units.map((unit) => unit.count), 1)
  }, [data])

  return (
    <section className="panel topic-frequency-panel" aria-live="polite">
      <div className="topic-frequency-header">
        <div>
          <h2>Exam topic frequency</h2>
          <p className="panel-intro">
            Estimated past-paper questions by unit — from ingested PYQ corpus only.
          </p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={reload}>
            Refresh
          </button>
        )}
      </div>

      {loading && (
        <div className="topic-frequency-loading">
          <span className="spinner" aria-hidden="true" />
          Loading topic frequency…
        </div>
      )}

      {!loading && error && (
        <div className={`topic-frequency-alert ${notFound ? 'alert-muted' : 'alert-error'}`} role="alert">
          <p>{error}</p>
          {!notFound && (
            <button type="button" className="text-btn" onClick={reload}>
              Retry
            </button>
          )}
        </div>
      )}

      {!loading && data && (
        <>
          {data.coverage_note && (
            <div
              className={
                isPartialCoverage(data.coverage_note)
                  ? 'coverage-banner coverage-partial'
                  : 'coverage-banner coverage-full'
              }
              role="status"
            >
              {data.coverage_note}
            </div>
          )}

          <p className="topic-frequency-total">
            <span className="topic-frequency-total-label">Estimated questions</span>
            <span className="topic-frequency-total-value">{data.total_questions_estimated}</span>
          </p>

          {data.units.length === 0 ? (
            <p className="muted">No past-paper units indexed for this course yet.</p>
          ) : (
            <div className="topic-frequency-chart">
              {data.units.map((unit, unitIndex) => {
                const barWidth = Math.round((unit.count / maxUnitCount) * 100)
                return (
                  <details key={unit.unit} className="topic-unit-row card-hover" open={data.units.length <= 3}>
                    <summary className="topic-unit-summary">
                      <span className="topic-unit-label">
                        Unit {unit.unit}: {unit.title}
                      </span>
                      <span className="topic-unit-count">{unit.count}</span>
                    </summary>

                    <div className="topic-bar-track" aria-hidden="true">
                      <div
                        className="topic-bar-fill topic-bar-grow"
                        style={
                          {
                            '--bar-width': `${barWidth}%`,
                            '--bar-delay': `${unitIndex * 40}ms`,
                          } as CSSProperties
                        }
                      />
                    </div>

                    {unit.sections.length > 0 && (
                      <ul className="topic-section-list">
                        {unit.sections.map((section) => (
                          <li key={`${unit.unit}-${section.section_title}`}>
                            <span className="topic-section-title">{section.section_title}</span>
                            <span className="topic-section-count">{section.count}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </details>
                )
              })}
            </div>
          )}

          {data.source_documents.length > 0 && (
            <p className="topic-frequency-sources muted">
              Sources:{' '}
              {data.source_documents
                .map((doc) => `${doc.filename} (${doc.readable_pages.length} readable pages)`)
                .join('; ')}
            </p>
          )}
        </>
      )}
    </section>
  )
}
