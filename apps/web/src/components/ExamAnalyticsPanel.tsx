import { useMemo, useState } from 'react'

import type { ExamAnalyticsSort } from '../api/examAnalyticsClient'
import { isExamPreset } from '../constants/queryPresets'
import { useExamAnalytics } from '../hooks/useExamAnalytics'
import type { ExamHeatmapSource, QueryPreset } from '../types'
import { ExamAnswerDrawer } from './ExamAnswerDrawer'

type DrawerTarget = {
  conceptId: string
  structureNodeId?: string
  label: string
}

interface ExamAnalyticsPanelProps {
  courseId: string
  refreshToken?: number
  queryPreset?: QueryPreset
  heatmapSource?: ExamHeatmapSource
  onSelectExamPreset?: () => void
}

function formatTrend(trend: number | null): string {
  if (trend == null) return '—'
  if (trend > 0.05) return '↑ rising'
  if (trend < -0.05) return '↓ falling'
  return '→ stable'
}

function formatPct(value: number): string {
  return `${value.toFixed(1)}%`
}

function nodeIdForUnit(unit: { unit_id: string }): string {
  return unit.unit_id
}

function nodeIdForPart(part: { part_id: string }): string {
  return part.part_id
}

function nodeIdForSubtopic(subtopic: { subtopic_id: string }): string {
  return subtopic.subtopic_id
}

function primaryConceptId(mappedIds: string[]): string | null {
  return mappedIds[0] ?? null
}

export function ExamAnalyticsPanel({
  courseId,
  refreshToken = 0,
  queryPreset = 'study',
  heatmapSource,
  onSelectExamPreset,
}: ExamAnalyticsPanelProps) {
  const [sort, setSort] = useState<ExamAnalyticsSort>('weightage_desc')
  const [drawerTarget, setDrawerTarget] = useState<DrawerTarget | null>(null)
  const { data, loading, error, notFound, reload } = useExamAnalytics(courseId, refreshToken, {
    sort,
  })

  const maxWeightage = useMemo(() => {
    if (!data?.concepts.length) return 1
    return Math.max(...data.concepts.map((row) => row.weightage_pct), 1)
  }, [data])

  const openConcept = (conceptId: string, label: string, structureNodeId?: string) => {
    setDrawerTarget({ conceptId, label, structureNodeId })
  }

  const openNode = (
    nodeId: string,
    title: string,
    mappedConceptIds: string[],
  ) => {
    const conceptId = primaryConceptId(mappedConceptIds)
    if (!conceptId) return
    openConcept(conceptId, title, nodeId)
  }

  return (
    <section className="panel exam-analytics-panel" aria-live="polite">
      <div className="exam-analytics-header">
        <div>
          <h2>Exam analytics</h2>
          <p className="panel-intro">
            Emergent concepts from past papers — marks-weighted frequency and syllabus mapping.
          </p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={reload}>
            Refresh
          </button>
        )}
      </div>

      {heatmapSource === 'parsed' && (
        <p className="muted exam-analytics-parsed-source" role="status">
          Parsed from past papers
        </p>
      )}

      {loading && (
        <div className="exam-analytics-loading">
          <span className="spinner" aria-hidden="true" />
          Loading exam analytics…
        </div>
      )}

      {!loading && error && (
        <div className={`exam-analytics-alert ${notFound ? 'alert-muted' : 'alert-error'}`} role="alert">
          <p>{error}</p>
          {!notFound && (
            <button type="button" className="text-btn" onClick={reload}>
              Retry
            </button>
          )}
        </div>
      )}

      {!loading && data && !data.analytics_ready && (
        <div className="exam-analytics-empty" role="status">
          <p>No parsed past-paper questions yet.</p>
          <ul className="exam-analytics-empty-steps">
            <li>Upload a PDF using the Past paper document type</li>
            <li>Wait for indexing to finish</li>
            <li>Refresh this panel to see concept analytics</li>
          </ul>
        </div>
      )}

      {!loading && data?.analytics_ready && (
        <>
          <div className="exam-analytics-summary">
            <span>
              <strong>{data.summary.question_count}</strong> questions
            </span>
            <span>
              <strong>{data.summary.concept_count}</strong> concepts
            </span>
            <span>
              <strong>{data.summary.distinct_papers}</strong> papers
            </span>
            {data.tier === 3 && <span className="exam-analytics-tier-badge">Tier 3 · mapped</span>}
          </div>

          {data.tier === 3 && data.structure?.units.length ? (
            <div className="exam-analytics-structure">
              <h3 className="exam-analytics-section-title">Syllabus tree</h3>
              <p className="muted exam-analytics-section-intro">
                Tap a unit, part, or topic to get a scoped answer from your study materials.
              </p>
              <ul className="exam-structure-tree">
                {data.structure.units.map((unit) => (
                  <li key={unit.unit_id} className="exam-structure-unit">
                    <button
                      type="button"
                      className="exam-structure-node-btn"
                      disabled={unit.mapped_concept_ids.length === 0}
                      onClick={() =>
                        openNode(nodeIdForUnit(unit), unit.title, unit.mapped_concept_ids)
                      }
                    >
                      <span className="exam-structure-node-title">{unit.title}</span>
                      <span className="exam-structure-node-metrics">
                        {formatPct(unit.weightage_pct)} · {unit.unique_question_count} q
                      </span>
                    </button>
                    {unit.parts?.map((part) => (
                      <ul key={part.part_id} className="exam-structure-part-list">
                        <li>
                          <button
                            type="button"
                            className="exam-structure-node-btn exam-structure-node-nested"
                            disabled={part.mapped_concept_ids.length === 0}
                            onClick={() =>
                              openNode(nodeIdForPart(part), part.title, part.mapped_concept_ids)
                            }
                          >
                            <span className="exam-structure-node-title">{part.title}</span>
                            <span className="exam-structure-node-metrics">
                              {formatPct(part.weightage_pct)} · {part.unique_question_count} q
                            </span>
                          </button>
                          <ul className="exam-structure-subtopic-list">
                            {part.subtopics.map((subtopic) => (
                              <li key={subtopic.subtopic_id}>
                                <button
                                  type="button"
                                  className="exam-structure-node-btn exam-structure-node-nested"
                                  disabled={subtopic.mapped_concept_ids.length === 0}
                                  onClick={() =>
                                    openNode(
                                      nodeIdForSubtopic(subtopic),
                                      subtopic.title,
                                      subtopic.mapped_concept_ids,
                                    )
                                  }
                                >
                                  <span className="exam-structure-node-title">{subtopic.title}</span>
                                  <span className="exam-structure-node-metrics">
                                    {formatPct(subtopic.weightage_pct)} · {subtopic.unique_question_count}{' '}
                                    q
                                  </span>
                                </button>
                              </li>
                            ))}
                          </ul>
                        </li>
                      </ul>
                    ))}
                    {unit.subtopics?.map((subtopic) => (
                      <ul key={subtopic.subtopic_id} className="exam-structure-subtopic-list">
                        <li>
                          <button
                            type="button"
                            className="exam-structure-node-btn exam-structure-node-nested"
                            disabled={subtopic.mapped_concept_ids.length === 0}
                            onClick={() =>
                              openNode(
                                nodeIdForSubtopic(subtopic),
                                subtopic.title,
                                subtopic.mapped_concept_ids,
                              )
                            }
                          >
                            <span className="exam-structure-node-title">{subtopic.title}</span>
                            <span className="exam-structure-node-metrics">
                              {formatPct(subtopic.weightage_pct)} · {subtopic.unique_question_count} q
                            </span>
                          </button>
                        </li>
                      </ul>
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="exam-analytics-concepts">
            <div className="exam-analytics-concepts-header">
              <h3 className="exam-analytics-section-title">Top concepts</h3>
              <label className="exam-analytics-sort">
                <span className="muted">Sort</span>
                <select
                  value={sort}
                  onChange={(event) => setSort(event.target.value as ExamAnalyticsSort)}
                >
                  <option value="weightage_desc">Weightage</option>
                  <option value="count_desc">Question count</option>
                  <option value="label_asc">Label A–Z</option>
                </select>
              </label>
            </div>

            {data.concepts.length === 0 ? (
              <p className="muted" role="status">
                No classified concepts yet.
              </p>
            ) : (
              <ul className="exam-concept-list">
                {data.concepts.map((concept) => {
                  const barWidth = Math.round((concept.weightage_pct / maxWeightage) * 100)
                  return (
                    <li key={concept.concept_id} className="exam-concept-row card-hover">
                      <button
                        type="button"
                        className="exam-concept-row-btn"
                        onClick={() => openConcept(concept.concept_id, concept.label)}
                      >
                        <div className="exam-concept-row-header">
                          <span className="exam-concept-rank">#{concept.rank}</span>
                          <span className="exam-concept-label">{concept.label}</span>
                          <span className="exam-concept-weightage">{formatPct(concept.weightage_pct)}</span>
                        </div>
                        <div className="topic-bar-track" aria-hidden="true">
                          <div
                            className="topic-bar-fill topic-bar-grow"
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                        <div className="exam-concept-meta muted">
                          <span>{concept.unique_question_count} questions</span>
                          <span>{formatTrend(concept.trend_slope)}</span>
                          <span>{concept.paper_reach} papers</span>
                        </div>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          {data.tier === 3 && (data.unmapped_concepts?.length ?? 0) > 0 && (
            <section className="exam-analytics-unmapped">
              <h3 className="exam-analytics-section-title">Unmapped concepts</h3>
              <p className="muted exam-analytics-section-intro">
                Exam concepts with no syllabus node match — syllabus gap signal.
              </p>
              <ul className="exam-unmapped-list">
                {data.unmapped_concepts!.map((concept) => (
                  <li key={concept.concept_id}>
                    <button
                      type="button"
                      className="text-btn exam-unmapped-btn"
                      onClick={() => openConcept(concept.concept_id, concept.label)}
                    >
                      {concept.label}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {!isExamPreset(queryPreset) && onSelectExamPreset && (
            <button type="button" className="text-btn exam-mode-link" onClick={onSelectExamPreset}>
              Switch to Exam mode to practice past papers
            </button>
          )}
        </>
      )}

      <ExamAnswerDrawer
        courseId={courseId}
        conceptId={drawerTarget?.conceptId}
        structureNodeId={drawerTarget?.structureNodeId}
        label={drawerTarget?.label}
        open={drawerTarget != null}
        onClose={() => setDrawerTarget(null)}
      />
    </section>
  )
}
