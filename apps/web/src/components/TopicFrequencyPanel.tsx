import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'

import { fetchPastPaperSources } from '../api/documentsClient'
import { useTopicFrequency } from '../hooks/useTopicFrequency'
import { isExamPreset } from '../constants/queryPresets'
import type { ExamHeatmapSource, QueryPreset } from '../types'
import {
  canToggleSectionBreakdown,
  coverageBannerClass,
  formatTopicUnitLabel,
  shouldDefaultShowSectionBreakdown,
  topicFrequencyEmptyMessage,
  topicFrequencyHasSectionDetail,
} from '../utils/courseLabels'

interface TopicFrequencyPanelProps {
  courseId: string
  refreshToken?: number
  queryPreset?: QueryPreset
  heatmapSource?: ExamHeatmapSource
  onSelectExamPreset?: () => void
}

export function TopicFrequencyPanel({
  courseId,
  refreshToken = 0,
  queryPreset = 'study',
  heatmapSource,
  onSelectExamPreset,
}: TopicFrequencyPanelProps) {
  const [showSectionBreakdown, setShowSectionBreakdown] = useState(false)
  const [breakdownInitialized, setBreakdownInitialized] = useState(false)
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([])
  const [pastPaperSources, setPastPaperSources] = useState<
    Awaited<ReturnType<typeof fetchPastPaperSources>>
  >([])
  const documentIds = selectedSourceIds.length > 0 ? selectedSourceIds : undefined

  const { data, loading, error, notFound, reload } = useTopicFrequency(courseId, refreshToken, {
    sectionDetail: showSectionBreakdown,
    documentIds,
  })

  const loadSources = useCallback(async () => {
    try {
      const rows = await fetchPastPaperSources(courseId)
      setPastPaperSources(rows)
      setSelectedSourceIds((current) => {
        const valid = current.filter((id) => rows.some((row) => row.document_id === id))
        return valid.length > 0 ? valid : rows.map((row) => row.document_id)
      })
    } catch {
      setPastPaperSources([])
    }
  }, [courseId])

  useEffect(() => {
    void loadSources()
  }, [loadSources, refreshToken])

  const toggleSource = (documentId: string) => {
    setSelectedSourceIds((current) => {
      if (current.includes(documentId)) {
        const next = current.filter((id) => id !== documentId)
        return next.length > 0 ? next : current
      }
      return [...current, documentId]
    })
  }

  useEffect(() => {
    if (!data || breakdownInitialized) return
    setShowSectionBreakdown(shouldDefaultShowSectionBreakdown(data.units))
    setBreakdownInitialized(true)
  }, [data, breakdownInitialized])

  useEffect(() => {
    setBreakdownInitialized(false)
    setShowSectionBreakdown(false)
  }, [courseId, refreshToken])

  const maxUnitCount = useMemo(() => {
    if (!data?.units.length) return 1
    return Math.max(...data.units.map((unit) => unit.count), 1)
  }, [data])

  const emptyMessage = data
    ? topicFrequencyEmptyMessage(
        data.total_questions_estimated,
        data.units.length,
        data.source_documents.length,
        data.coverage_note,
      )
    : null

  const showBreakdownToggle = data
    ? canToggleSectionBreakdown(data.units, data.total_questions_estimated)
    : false

  const sectionsVisible =
    showSectionBreakdown && data ? topicFrequencyHasSectionDetail(data.units) : false

  return (
    <section className="panel topic-frequency-panel" aria-live="polite">
      <div className="topic-frequency-header">
        <div>
          <h2>Exam topic frequency</h2>
          <p className="panel-intro">
            Estimated past-paper questions by topic — matched to your course outline when possible.
          </p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={reload}>
            Refresh
          </button>
        )}
      </div>

      {heatmapSource === 'parsed' && (
        <p className="muted topic-frequency-parsed-source" role="status">
          Parsed from past papers
        </p>
      )}

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
            <div className={coverageBannerClass(data.coverage_note)} role="status">
              {data.coverage_note}
            </div>
          )}

          {data.units.length === 0 ? (
            <div className="topic-frequency-empty" role="status">
              <p>{emptyMessage}</p>
              {data.total_questions_estimated === 0 && (
                <ul className="topic-frequency-empty-steps">
                  <li>Upload a PDF using the Past paper document type</li>
                  <li>Wait for indexing to finish</li>
                  <li>Refresh this panel to see topic bars</li>
                </ul>
              )}
            </div>
          ) : (
            <>
              <p className="topic-frequency-total">
                <span className="topic-frequency-total-label">Estimated questions</span>
                <span className="topic-frequency-total-value">{data.total_questions_estimated}</span>
              </p>

              {showBreakdownToggle && (
                <button
                  type="button"
                  className="topic-section-toggle text-btn"
                  aria-pressed={showSectionBreakdown}
                  onClick={() => setShowSectionBreakdown((open) => !open)}
                >
                  {showSectionBreakdown ? 'Hide section breakdown' : 'Show section breakdown'}
                </button>
              )}

              <div className="topic-frequency-chart">
                {data.units.map((unit, unitIndex) => {
                  const barWidth = Math.round((unit.count / maxUnitCount) * 100)
                  return (
                    <div key={`${unit.unit}-${unit.title}`} className="topic-unit-row card-hover">
                      <div className="topic-unit-header">
                        <span className="topic-unit-label">{formatTopicUnitLabel(unit)}</span>
                        <span className="topic-unit-count">{unit.count}</span>
                      </div>

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

                      {sectionsVisible && (unit.sections ?? []).length > 0 && (
                        <ul className="topic-section-list">
                          {(unit.sections ?? []).map((section) => (
                            <li key={`${unit.unit}-${section.section_title}`}>
                              <span className="topic-section-title">{section.section_title}</span>
                              <span className="topic-section-count">{section.count}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {pastPaperSources.length > 0 && (
            <section className="exam-past-paper-sources topic-frequency-sources-panel">
              <h3 className="exam-analytics-section-title">Past-paper sources</h3>
              <p className="muted exam-analytics-section-intro">
                Choose which PDFs to include in exam predictions.
              </p>
              <ul className="exam-sources-list">
                {pastPaperSources.map((source) => (
                  <li key={source.document_id} className="exam-source-row">
                    <label className="exam-source-select">
                      <input
                        type="checkbox"
                        checked={selectedSourceIds.includes(source.document_id)}
                        onChange={() => toggleSource(source.document_id)}
                      />
                      <span className="exam-source-name">{source.filename}</span>
                      <span className="muted exam-source-meta">
                        {source.parsed_question_count} parsed · {source.status}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {pastPaperSources.length > 0 && (
            <p className="topic-frequency-sources muted">
              Active sources:{' '}
              {pastPaperSources
                .filter((source) => selectedSourceIds.includes(source.document_id))
                .map((source) => source.filename)
                .join('; ')}
            </p>
          )}

          {!isExamPreset(queryPreset) &&
            pastPaperSources.length > 0 &&
            onSelectExamPreset && (
              <button type="button" className="text-btn exam-mode-link" onClick={onSelectExamPreset}>
                Switch to Exam mode to practice past papers
              </button>
            )}
        </>
      )}
    </section>
  )
}
