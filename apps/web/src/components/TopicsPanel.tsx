import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  bulkCreateStudyTopics,
  createStudyTopic,
  patchDocumentTopic,
  patchStructureMode,
  StudyTopicsApiError,
} from '../api/studyTopicsClient'
import { DOCUMENT_KIND_OPTIONS } from '../constants/documentKinds'
import { isStudyPreset } from '../constants/queryPresets'
import type {
  QueryPreset,
  StudyLayoutResponse,
  StudyLayoutSource,
  StudyTopic,
} from '../types'

interface TopicsPanelProps {
  courseId: string
  layout: StudyLayoutResponse | null
  layoutLoading: boolean
  layoutError: string | null
  topics: StudyTopic[]
  topicsLoading: boolean
  topicsError: string | null
  queryPreset: QueryPreset
  selectedTopicIds: ReadonlySet<string>
  onSelectedTopicIdsChange: (ids: Set<string>) => void
  onReload: () => void
}

function formatDocKindLabel(docKind: string): string {
  const match = DOCUMENT_KIND_OPTIONS.find((option) => option.value === docKind)
  return match?.label ?? docKind
}

function isSelectable(source: StudyLayoutSource): boolean {
  return source.status === 'ready'
}

function parseChapterTitles(raw: string): string[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

export function TopicsPanel({
  courseId,
  layout,
  layoutLoading,
  layoutError,
  topics,
  topicsLoading,
  topicsError,
  queryPreset,
  selectedTopicIds,
  onSelectedTopicIdsChange,
  onReload,
}: TopicsPanelProps) {
  const sources = layout?.sources ?? []
  const [assignments, setAssignments] = useState<Record<string, string | null>>({})
  const [newTopicTitle, setNewTopicTitle] = useState('')
  const [chapterPaste, setChapterPaste] = useState('')
  const [showPastePanel, setShowPastePanel] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    setAssignments((prev) => {
      const next = { ...prev }
      for (const source of sources) {
        if (source.topic_id !== undefined) {
          next[source.document_id] = source.topic_id
        }
      }
      return next
    })
  }, [sources])

  const loading = layoutLoading || topicsLoading
  const error = layoutError ?? topicsError
  const showTopicScope = isStudyPreset(queryPreset)

  const docsByTopicId = useMemo(() => {
    const grouped = new Map<string, StudyLayoutSource[]>()
    for (const topic of topics) {
      grouped.set(topic.id, [])
    }

    const unassigned: StudyLayoutSource[] = []
    for (const source of sources) {
      const topicId = assignments[source.document_id] ?? source.topic_id ?? null
      if (topicId && grouped.has(topicId)) {
        grouped.get(topicId)?.push(source)
      } else {
        unassigned.push(source)
      }
    }

    return { grouped, unassigned }
  }, [assignments, sources, topics])

  const handleReload = useCallback(() => {
    onReload()
  }, [onReload])

  const promoteToOrganizedIfNeeded = useCallback(async () => {
    if (layout?.structure_mode === 'corpus') {
      await patchStructureMode(courseId, 'organized')
    }
  }, [courseId, layout?.structure_mode])

  const runAction = useCallback(
    async (label: string, action: () => Promise<void>) => {
      setBusyAction(label)
      setActionError(null)
      try {
        await action()
        handleReload()
      } catch (err) {
        if (err instanceof StudyTopicsApiError) {
          setActionError(`${err.status}: ${err.message}`)
        } else {
          setActionError(err instanceof Error ? err.message : 'Action failed')
        }
      } finally {
        setBusyAction(null)
      }
    },
    [handleReload],
  )

  const handleAddTopic = (event: FormEvent) => {
    event.preventDefault()
    const title = newTopicTitle.trim()
    if (!title) return

    void runAction('add-topic', async () => {
      await promoteToOrganizedIfNeeded()
      await createStudyTopic(courseId, title, topics.length)
      setNewTopicTitle('')
    })
  }

  const handleBulkPaste = (event: FormEvent) => {
    event.preventDefault()
    const titles = parseChapterTitles(chapterPaste)
    if (titles.length === 0) return

    void runAction('bulk-topics', async () => {
      await bulkCreateStudyTopics(courseId, titles)
      setChapterPaste('')
      setShowPastePanel(false)
    })
  }

  const handleAssignDocument = async (documentId: string, topicId: string | null) => {
    setBusyAction(`assign-${documentId}`)
    setActionError(null)
    try {
      const response = await patchDocumentTopic(documentId, topicId)
      setAssignments((prev) => ({
        ...prev,
        [documentId]: response.topic_id,
      }))
    } catch (err) {
      if (err instanceof StudyTopicsApiError) {
        setActionError(`${err.status}: ${err.message}`)
      } else {
        setActionError(err instanceof Error ? err.message : 'Could not assign document')
      }
    } finally {
      setBusyAction(null)
    }
  }

  const handleToggleTopic = (topic: StudyTopic, checked: boolean) => {
    const next = new Set(selectedTopicIds)
    if (checked) {
      next.add(topic.id)
    } else {
      next.delete(topic.id)
    }
    onSelectedTopicIdsChange(next)
  }

  const handleSelectAllTopics = () => {
    onSelectedTopicIdsChange(new Set(topics.map((topic) => topic.id)))
  }

  const handleClearTopics = () => {
    onSelectedTopicIdsChange(new Set())
  }

  const selectedTopicCount = topics.filter((topic) => selectedTopicIds.has(topic.id)).length

  return (
    <section className="panel topics-panel" aria-live="polite">
      <div className="sources-panel-header">
        <div>
          <div className="sources-panel-title-row">
            <h2>Your topics</h2>
            <span className="organized-study-badge" role="status">
              Organized Study
            </span>
          </div>
          <p className="panel-intro">
            Group PDFs by topic — check topics to limit answers to those documents.
          </p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={handleReload}>
            Refresh
          </button>
        )}
      </div>

      {loading && (
        <div className="sources-panel-loading">
          <span className="spinner" aria-hidden="true" />
          Loading topics…
        </div>
      )}

      {!loading && error && (
        <div className="sources-panel-alert alert-error" role="alert">
          <p>{error}</p>
          <button type="button" className="text-btn" onClick={handleReload}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && (
        <>
          {showTopicScope && topics.length > 0 && (
            <div className="sources-selection-toolbar">
              <p className="sources-selection-count" role="status">
                {selectedTopicCount} of {topics.length} topics selected
              </p>
              <div className="sources-selection-actions">
                <button type="button" className="text-btn" onClick={handleSelectAllTopics}>
                  Select all
                </button>
                <button type="button" className="text-btn" onClick={handleClearTopics}>
                  Clear
                </button>
              </div>
            </div>
          )}

          {topics.length === 0 && (
            <div className="sources-panel-empty" role="status">
              <p>No topics yet for {courseId}.</p>
              <p className="muted">Add a topic below or paste a chapter list to get started.</p>
            </div>
          )}

          {topics.length > 0 && (
            <ul className="topics-list">
              {topics.map((topic) => {
                const assignedDocs = docsByTopicId.grouped.get(topic.id) ?? []
                const checked = selectedTopicIds.has(topic.id)

                return (
                  <li key={topic.id} className="topic-row card-hover">
                    <details className="topic-details">
                      <summary className="topic-summary">
                        {showTopicScope && (
                          <label
                            className="topic-checkbox-label"
                            onClick={(event) => event.stopPropagation()}
                          >
                            <input
                              type="checkbox"
                              className="source-checkbox"
                              checked={checked}
                              aria-label={`Include topic ${topic.title}`}
                              onChange={(event) =>
                                handleToggleTopic(topic, event.target.checked)
                              }
                            />
                          </label>
                        )}
                        <span className="topic-title">{topic.title}</span>
                        <span className="topic-doc-count muted">
                          {assignedDocs.length} PDF{assignedDocs.length === 1 ? '' : 's'}
                        </span>
                      </summary>

                      {assignedDocs.length > 0 ? (
                        <ul className="topic-assigned-docs">
                          {assignedDocs.map((source) => (
                            <li key={source.document_id} className="topic-doc-row">
                              <span className="topic-doc-name">{source.filename}</span>
                              <select
                                className="topic-assign-select"
                                value={topic.id}
                                disabled={busyAction === `assign-${source.document_id}`}
                                aria-label={`Assign ${source.filename} to topic`}
                                onChange={(event) => {
                                  const value = event.target.value
                                  void handleAssignDocument(
                                    source.document_id,
                                    value === '' ? null : value,
                                  )
                                }}
                              >
                                {topics.map((option) => (
                                  <option key={option.id} value={option.id}>
                                    {option.title}
                                  </option>
                                ))}
                                <option value="">Unassigned</option>
                              </select>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="topic-empty-docs muted">No PDFs assigned yet.</p>
                      )}
                    </details>
                  </li>
                )
              })}
            </ul>
          )}

          {docsByTopicId.unassigned.length > 0 && (
            <section className="topic-unassigned-panel">
              <h3>Unassigned PDFs</h3>
              <p className="muted topic-unassigned-hint">
                Assign each document to a topic for scoped study.
              </p>
              <ul className="topic-unassigned-list">
                {docsByTopicId.unassigned.map((source) => (
                  <li key={source.document_id} className="topic-doc-row">
                    <span className="topic-doc-main">
                      <span className="topic-doc-name">{source.filename}</span>
                      <span className={`source-doc-kind-badge source-doc-kind-${source.doc_kind}`}>
                        {formatDocKindLabel(source.doc_kind)}
                      </span>
                    </span>
                    <select
                      className="topic-assign-select"
                      value=""
                      disabled={
                        !isSelectable(source) || busyAction === `assign-${source.document_id}`
                      }
                      aria-label={`Assign ${source.filename} to topic`}
                      onChange={(event) => {
                        const value = event.target.value
                        if (!value) return
                        void handleAssignDocument(source.document_id, value)
                      }}
                    >
                      <option value="">Choose topic…</option>
                      {topics.map((topic) => (
                        <option key={topic.id} value={topic.id}>
                          {topic.title}
                        </option>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <form className="topic-add-form" onSubmit={handleAddTopic}>
            <label className="field">
              <span>Add topic</span>
              <div className="topic-add-row">
                <input
                  type="text"
                  value={newTopicTitle}
                  onChange={(event) => setNewTopicTitle(event.target.value)}
                  placeholder="Thermodynamics"
                  disabled={busyAction === 'add-topic'}
                />
                <button
                  type="submit"
                  className="text-btn topic-add-btn"
                  disabled={!newTopicTitle.trim() || busyAction === 'add-topic'}
                >
                  {busyAction === 'add-topic' ? 'Adding…' : 'Add'}
                </button>
              </div>
            </label>
          </form>

          <div className="topic-paste-panel">
            <button
              type="button"
              className="text-btn"
              onClick={() => setShowPastePanel((open) => !open)}
            >
              {showPastePanel ? 'Hide chapter list' : 'Paste chapter list'}
            </button>

            {showPastePanel && (
              <form className="topic-paste-form" onSubmit={handleBulkPaste}>
                <label className="field">
                  <span>One topic title per line</span>
                  <textarea
                    value={chapterPaste}
                    onChange={(event) => setChapterPaste(event.target.value)}
                    rows={5}
                    placeholder={'Unit 1: Introduction\nUnit 2: Bonding\nUnit 3: Reactions'}
                    disabled={busyAction === 'bulk-topics'}
                  />
                </label>
                <button
                  type="submit"
                  className="submit-btn topic-paste-submit"
                  disabled={
                    parseChapterTitles(chapterPaste).length === 0 || busyAction === 'bulk-topics'
                  }
                >
                  {busyAction === 'bulk-topics' ? 'Creating…' : 'Create topics'}
                </button>
              </form>
            )}
          </div>

          {actionError && (
            <div className="sources-panel-alert alert-error" role="alert">
              <p>{actionError}</p>
            </div>
          )}
        </>
      )}
    </section>
  )
}
