import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react'

import type { PastPaperSource } from '../api/documentsClient'
import { deleteCourseDocument, fetchPastPaperSources } from '../api/documentsClient'
import type { ExamAnalyticsSort, SyllabusPrimaryBlock } from '../api/examAnalyticsClient'
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
  onConceptsLoaded?: (labels: string[]) => void
  onSourcesChanged?: () => void
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

function formatYears(years: string[]): string {
  if (years.length === 0) return '—'
  if (years.length === 1) return years[0]
  return `${years[0]}–${years[years.length - 1]}`
}

function sameIdSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const left = [...a].sort()
  const right = [...b].sort()
  return left.every((id, index) => id === right[index])
}

function SyllabusPrimarySection({ syllabus }: { syllabus: SyllabusPrimaryBlock }) {
  const maxUnitPct = useMemo(
    () => Math.max(...syllabus.units.map((unit) => unit.subpart_pct), 1),
    [syllabus.units],
  )
  const matrixUnits = useMemo(() => {
    const units = new Set<string>()
    for (const row of Object.values(syllabus.year_unit_matrix)) {
      for (const unit of Object.keys(row)) units.add(unit)
    }
    return Array.from(units).sort()
  }, [syllabus.year_unit_matrix])
  const matrixYears = useMemo(
    () => Object.keys(syllabus.year_unit_matrix).sort(),
    [syllabus.year_unit_matrix],
  )

  return (
    <div className="exam-syllabus-primary">
      <div className="exam-syllabus-stats">
        <div className="exam-syllabus-stat">
          <span className="exam-syllabus-stat-value">{syllabus.summary.paper_count}</span>
          <span className="exam-syllabus-stat-label">Past papers</span>
        </div>
        <div className="exam-syllabus-stat">
          <span className="exam-syllabus-stat-value">{syllabus.summary.main_question_count}</span>
          <span className="exam-syllabus-stat-label">Main questions</span>
        </div>
        <div className="exam-syllabus-stat">
          <span className="exam-syllabus-stat-value">{syllabus.summary.subpart_count}</span>
          <span className="exam-syllabus-stat-label">Sub-parts</span>
        </div>
        <div className="exam-syllabus-stat">
          <span className="exam-syllabus-stat-value">{formatYears(syllabus.summary.years)}</span>
          <span className="exam-syllabus-stat-label">Years</span>
        </div>
      </div>

      {syllabus.units.length > 0 && (
        <section className="exam-syllabus-card">
          <h3 className="exam-analytics-section-title">Distribution by syllabus unit</h3>
          <p className="muted exam-analytics-section-intro">
            Share of all {syllabus.summary.subpart_count} sub-parts and main-question counts.
          </p>
          <ul className="exam-syllabus-unit-list">
            {syllabus.units.map((unit) => {
              const barWidth = Math.round((unit.subpart_pct / maxUnitPct) * 100)
              return (
                <li key={unit.unit} className="exam-syllabus-unit-row">
                  <div className="exam-syllabus-unit-header">
                    <span className="exam-syllabus-unit-name">{unit.unit}</span>
                    <span className="muted exam-syllabus-unit-meta">
                      {unit.subpart_count} sub · {formatPct(unit.subpart_pct)} · {unit.main_count} main (
                      {formatPct(unit.main_pct)})
                    </span>
                  </div>
                  <div className="topic-bar-track" aria-hidden="true">
                    <div className="topic-bar-fill topic-bar-grow" style={{ width: `${barWidth}%` }} />
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {syllabus.top_topics.length > 0 && (
        <section className="exam-syllabus-card">
          <h3 className="exam-analytics-section-title">Top topics by frequency</h3>
          <ul className="exam-syllabus-topic-list">
            {syllabus.top_topics.map((topic, index) => (
              <li key={topic.name} className="exam-syllabus-topic-row">
                <span className="exam-concept-rank">#{index + 1}</span>
                <span className="exam-syllabus-topic-name">{topic.name}</span>
                <span className="exam-syllabus-topic-count">
                  {topic.count} ({formatPct(topic.pct)})
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {matrixYears.length > 0 && matrixUnits.length > 0 && (
        <section className="exam-syllabus-card">
          <h3 className="exam-analytics-section-title">Sub-parts by year and unit</h3>
          <div className="exam-syllabus-matrix-wrap">
            <table className="exam-syllabus-matrix">
              <thead>
                <tr>
                  <th scope="col">Year</th>
                  {matrixUnits.map((unit) => (
                    <th key={unit} scope="col">
                      {unit}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixYears.map((year) => (
                  <tr key={year}>
                    <th scope="row">{year}</th>
                    {matrixUnits.map((unit) => (
                      <td key={unit}>{syllabus.year_unit_matrix[year]?.[unit] ?? 0}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {syllabus.top_subtopics.length > 0 && (
        <section className="exam-syllabus-card">
          <h3 className="exam-analytics-section-title">Highest-yield subtopics</h3>
          <div className="exam-syllabus-matrix-wrap">
            <table className="exam-syllabus-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Subtopic</th>
                  <th scope="col" className="exam-syllabus-num">
                    Count
                  </th>
                  <th scope="col" className="exam-syllabus-num">
                    %
                  </th>
                </tr>
              </thead>
              <tbody>
                {syllabus.top_subtopics.map((row, index) => (
                  <tr key={row.name}>
                    <td>{index + 1}</td>
                    <td>{row.name}</td>
                    <td className="exam-syllabus-num">{row.count}</td>
                    <td className="exam-syllabus-num">{formatPct(row.pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {syllabus.papers_table.length > 0 && (
        <section className="exam-syllabus-card">
          <h3 className="exam-analytics-section-title">All papers</h3>
          <div className="exam-syllabus-matrix-wrap">
            <table className="exam-syllabus-table">
              <thead>
                <tr>
                  <th scope="col">Session</th>
                  <th scope="col">Code</th>
                  <th scope="col">Year</th>
                  <th scope="col">Format</th>
                  <th scope="col" className="exam-syllabus-num">
                    Main
                  </th>
                  <th scope="col" className="exam-syllabus-num">
                    Sub-parts
                  </th>
                </tr>
              </thead>
              <tbody>
                {syllabus.papers_table.map((paper) => (
                  <tr key={paper.paper_label}>
                    <td>{paper.session ?? '—'}</td>
                    <td>{paper.code ?? '—'}</td>
                    <td>{paper.year ?? '—'}</td>
                    <td>{paper.format ?? '—'}</td>
                    <td className="exam-syllabus-num">{paper.main}</td>
                    <td className="exam-syllabus-num">{paper.sub}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

function PastPaperSourcesBar({
  courseId,
  refreshToken,
  selectedSourceIds,
  onSelectedSourceIdsChange,
  onSourcesChanged,
}: {
  courseId: string
  refreshToken: number
  selectedSourceIds: string[]
  onSelectedSourceIdsChange: Dispatch<SetStateAction<string[]>>
  onSourcesChanged?: () => void
}) {
  const [sources, setSources] = useState<PastPaperSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const initializedRef = useRef(false)

  const loadSources = useCallback(async () => {
    setError(null)
    try {
      const rows = await fetchPastPaperSources(courseId)
      setSources(rows)
      if (rows.length === 0) {
        initializedRef.current = false
        onSelectedSourceIdsChange((current) => (current.length === 0 ? current : []))
        return
      }
      onSelectedSourceIdsChange((current) => {
        const valid = current.filter((id) => rows.some((row) => row.document_id === id))
        const next = valid.length > 0 ? valid : rows.map((row) => row.document_id)
        if (sameIdSet(current, next)) return current
        return next
      })
      initializedRef.current = true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load past-paper sources.')
    } finally {
      setLoading(false)
    }
  }, [courseId])

  useEffect(() => {
    if (sources.length === 0) {
      setLoading(true)
    }
    void loadSources()
  }, [courseId, refreshToken, loadSources])

  const toggleSource = (documentId: string) => {
    onSelectedSourceIdsChange((current) => {
      if (current.includes(documentId)) {
        const next = current.filter((id) => id !== documentId)
        return next.length > 0 ? next : current
      }
      return [...current, documentId]
    })
  }

  const handleDelete = async (source: PastPaperSource) => {
    setDeletingId(source.document_id)
    setError(null)
    try {
      await deleteCourseDocument(courseId, source.document_id)
      setSources((current) => current.filter((row) => row.document_id !== source.document_id))
      onSelectedSourceIdsChange((current) => {
        const next = current.filter((id) => id !== source.document_id)
        return next
      })
      setConfirmDeleteId(null)
      onSourcesChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete source.')
    } finally {
      setDeletingId(null)
    }
  }

  if (loading && sources.length === 0) {
    return <p className="muted exam-sources-loading">Loading past-paper sources…</p>
  }

  if (sources.length === 0) {
    return null
  }

  return (
    <section className="exam-past-paper-sources">
      <h3 className="exam-analytics-section-title">Past-paper sources</h3>
      <p className="muted exam-analytics-section-intro">
        Select which PDFs to include in analytics. Remove stray or duplicate uploads, then re-upload
        the OU bundle to refresh counts.
      </p>
      {error && (
        <p className="exam-sources-error" role="alert">
          {error}
        </p>
      )}
      <ul className="exam-sources-list">
        {sources.map((source) => {
          const selected = selectedSourceIds.includes(source.document_id)
          const confirming = confirmDeleteId === source.document_id
          return (
            <li key={source.document_id} className="exam-source-row">
              <label className="exam-source-select">
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => toggleSource(source.document_id)}
                />
                <span className="exam-source-name">{source.filename}</span>
                <span className="muted exam-source-meta">
                  {source.parsed_question_count} parsed · {source.status}
                </span>
              </label>
              {confirming ? (
                <div className="exam-source-delete-confirm">
                  <span className="muted">Delete this PDF?</span>
                  <button
                    type="button"
                    className="text-btn exam-source-delete"
                    disabled={deletingId === source.document_id}
                    onClick={() => void handleDelete(source)}
                  >
                    {deletingId === source.document_id ? 'Deleting…' : 'Confirm'}
                  </button>
                  <button
                    type="button"
                    className="text-btn"
                    disabled={deletingId === source.document_id}
                    onClick={() => setConfirmDeleteId(null)}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="text-btn exam-source-delete"
                  disabled={deletingId === source.document_id}
                  onClick={() => setConfirmDeleteId(source.document_id)}
                >
                  Delete
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function ExamAnalyticsPanel({
  courseId,
  refreshToken = 0,
  queryPreset = 'study',
  heatmapSource,
  onSelectExamPreset,
  onConceptsLoaded,
  onSourcesChanged,
}: ExamAnalyticsPanelProps) {
  const [sort, setSort] = useState<ExamAnalyticsSort>('weightage_desc')
  const [showAllConcepts, setShowAllConcepts] = useState(false)
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([])
  const [drawerTarget, setDrawerTarget] = useState<DrawerTarget | null>(null)
  const documentIds = useMemo(
    () => (selectedSourceIds.length > 0 ? selectedSourceIds : undefined),
    [selectedSourceIds],
  )
  const { data, loading, refreshing, error, notFound, reload } = useExamAnalytics(
    courseId,
    refreshToken,
    {
      sort,
      includeFlat: showAllConcepts,
      documentIds,
    },
  )

  const syllabus = data?.syllabus_primary
  const flatHidden = data?.pagination?.flat_hidden === true
  const showConcepts = !flatHidden || showAllConcepts

  const maxWeightage = useMemo(() => {
    if (!data?.concepts.length) return 1
    return Math.max(...data.concepts.map((row) => row.weightage_pct), 1)
  }, [data])

  useEffect(() => {
    if (!onConceptsLoaded || !data?.concepts.length) return
    onConceptsLoaded(data.concepts.slice(0, 2).map((concept) => concept.label))
  }, [data, onConceptsLoaded])

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
            {syllabus
              ? 'Syllabus-weighted past-paper breakdown with emergent concept analytics on demand.'
              : 'Emergent concepts from past papers — marks-weighted frequency and syllabus mapping.'}
          </p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={reload}>
            Refresh
          </button>
        )}
        {refreshing && (
          <span className="muted exam-analytics-refreshing" role="status">
            Updating…
          </span>
        )}
      </div>

      <PastPaperSourcesBar
        courseId={courseId}
        refreshToken={refreshToken}
        selectedSourceIds={selectedSourceIds}
        onSelectedSourceIdsChange={setSelectedSourceIds}
        onSourcesChanged={onSourcesChanged}
      />

      {heatmapSource === 'parsed' && (
        <p className="muted exam-analytics-parsed-source" role="status">
          Parsed from past papers
        </p>
      )}

      {loading && !data && (
        <div className="exam-analytics-loading">
          <span className="spinner" aria-hidden="true" />
          Loading exam analytics…
        </div>
      )}

      {!loading && error && !data && (
        <div className={`exam-analytics-alert ${notFound ? 'alert-muted' : 'alert-error'}`} role="alert">
          <p>{error}</p>
          {!notFound && (
            <button type="button" className="text-btn" onClick={reload}>
              Retry
            </button>
          )}
        </div>
      )}

      {error && data && (
        <div className="exam-analytics-alert alert-error" role="alert">
          <p>{error}</p>
          <button type="button" className="text-btn" onClick={reload}>
            Retry
          </button>
        </div>
      )}

      {data && !data.analytics_ready && (
        <div className="exam-analytics-empty" role="status">
          <p>No parsed past-paper questions yet.</p>
          <ul className="exam-analytics-empty-steps">
            <li>Upload a PDF using the Past paper document type</li>
            <li>Wait for indexing to finish</li>
            <li>Refresh this panel to see concept analytics</li>
          </ul>
        </div>
      )}

      {data?.analytics_ready && (
        <>
          {!syllabus && (
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
          )}

          {syllabus && <SyllabusPrimarySection syllabus={syllabus} />}

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

          {flatHidden && (
            <div className="exam-analytics-flat-toggle">
              <button
                type="button"
                className="text-btn"
                onClick={() => setShowAllConcepts((value) => !value)}
              >
                {showAllConcepts ? 'Hide emergent concepts' : 'Show emergent concepts'}
              </button>
            </div>
          )}

          {showConcepts && (
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
                  {flatHidden ? 'Emergent concepts hidden — use the toggle above to expand.' : 'No classified concepts yet.'}
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
          )}

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
