import { useMemo } from 'react'

import { DOCUMENT_KIND_OPTIONS } from '../constants/documentKinds'
import type { StudyLayoutResponse, StudyLayoutSource } from '../types'

interface SourcesPanelProps {
  courseId: string
  layout: StudyLayoutResponse | null
  loading: boolean
  error: string | null
  selectedSourceIds: ReadonlySet<string>
  onSelectedSourceIdsChange: (ids: Set<string>) => void
  onReload: () => void
  onOrganizeByTopics?: () => void
  organizing?: boolean
  organizeError?: string | null
}

function formatDocKindLabel(docKind: string): string {
  const match = DOCUMENT_KIND_OPTIONS.find((option) => option.value === docKind)
  return match?.label ?? docKind
}

function formatStatusLabel(status: string): string {
  if (status === 'processing') return 'Indexing…'
  return 'Ready'
}

function isSelectable(source: StudyLayoutSource): boolean {
  return source.status === 'ready'
}

export function SourcesPanel({
  courseId,
  layout,
  loading,
  error,
  selectedSourceIds,
  onSelectedSourceIdsChange,
  onReload,
  onOrganizeByTopics,
  organizing = false,
  organizeError = null,
}: SourcesPanelProps) {
  const sources = layout?.sources ?? []

  const selectableSources = useMemo(
    () => sources.filter(isSelectable),
    [sources],
  )

  const selectedSelectableCount = useMemo(
    () => selectableSources.filter((source) => selectedSourceIds.has(source.document_id)).length,
    [selectableSources, selectedSourceIds],
  )

  const handleToggle = (source: StudyLayoutSource, checked: boolean) => {
    if (!isSelectable(source)) return
    const next = new Set(selectedSourceIds)
    if (checked) {
      next.add(source.document_id)
    } else {
      next.delete(source.document_id)
    }
    onSelectedSourceIdsChange(next)
  }

  const handleSelectAll = () => {
    onSelectedSourceIdsChange(new Set(selectableSources.map((source) => source.document_id)))
  }

  const handleClear = () => {
    onSelectedSourceIdsChange(new Set())
  }

  return (
    <section className="panel sources-panel" aria-live="polite">
      <div className="sources-panel-header">
        <div>
          <div className="sources-panel-title-row">
            <h2>Your sources</h2>
            <span className="quick-study-badge" role="status">
              Quick Study
            </span>
          </div>
          <p className="panel-intro">
            Choose which PDFs to search — answers cite pages from selected documents only.
          </p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={onReload}>
            Refresh
          </button>
        )}
      </div>

      {loading && (
        <div className="sources-panel-loading">
          <span className="spinner" aria-hidden="true" />
          Loading sources…
        </div>
      )}

      {!loading && error && (
        <div className="sources-panel-alert alert-error" role="alert">
          <p>{error}</p>
          <button type="button" className="text-btn" onClick={onReload}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && sources.length === 0 && (
        <div className="sources-panel-empty" role="status">
          <p>No documents indexed yet for {courseId}.</p>
          <p className="muted">Upload a PDF in the main column — notes, textbook, or syllabus work best.</p>
        </div>
      )}

      {!loading && !error && sources.length > 0 && (
        <>
          <div className="sources-selection-toolbar">
            <p className="sources-selection-count" role="status">
              {selectedSelectableCount} of {selectableSources.length} sources selected
            </p>
            {selectableSources.length > 0 && (
              <div className="sources-selection-actions">
                <button type="button" className="text-btn" onClick={handleSelectAll}>
                  Select all
                </button>
                <button type="button" className="text-btn" onClick={handleClear}>
                  Clear
                </button>
              </div>
            )}
          </div>

          <ul className="sources-list">
            {sources.map((source) => {
              const selectable = isSelectable(source)
              const checked = selectable && selectedSourceIds.has(source.document_id)

              return (
                <li key={source.document_id} className="source-row card-hover">
                  <label
                    className={`source-row-label ${selectable ? '' : 'is-disabled'}`}
                    title={selectable ? undefined : 'Indexing…'}
                  >
                    <input
                      type="checkbox"
                      className="source-checkbox"
                      checked={checked}
                      disabled={!selectable}
                      aria-label={`${selectable ? 'Include' : 'Exclude (indexing)'} ${source.filename}`}
                      onChange={(event) => handleToggle(source, event.target.checked)}
                    />
                    <span className="source-row-content">
                      <span className="source-row-main">
                        <span className="source-filename">{source.filename}</span>
                        <span className={`source-doc-kind-badge source-doc-kind-${source.doc_kind}`}>
                          {formatDocKindLabel(source.doc_kind)}
                        </span>
                      </span>
                      <span className="source-row-meta muted">
                        <span>{source.page_count} pages</span>
                        <span
                          className={`source-status source-status-${source.status}`}
                          role="status"
                        >
                          {source.status === 'processing' && (
                            <span className="spinner source-status-spinner" aria-hidden="true" />
                          )}
                          {formatStatusLabel(source.status)}
                        </span>
                      </span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>

          {onOrganizeByTopics && sources.length > 0 && (
            <div className="sources-organize-cta">
              <p className="muted">Want custom topic buckets instead of a flat PDF list?</p>
              <button
                type="button"
                className="submit-btn sources-organize-btn"
                disabled={organizing}
                onClick={onOrganizeByTopics}
              >
                {organizing ? 'Enabling…' : 'Organize by topics'}
              </button>
              {organizeError && (
                <div className="sources-panel-alert alert-error" role="alert">
                  <p>{organizeError}</p>
                  <p className="muted">
                    Ensure the API is running on port 8002 with Phase S migrations applied.
                  </p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}
