import { useCallback, useMemo, useState, type FormEvent } from 'react'

import {
  assignPartDocuments,
  assignSubtopicDocuments,
  assignUnitDocuments,
  confirmCourseStructure,
  CourseStructureApiError,
  importStructurePaste,
  importStructureSyllabus,
} from '../api/courseStructureClient'
import { DOCUMENT_KIND_OPTIONS } from '../constants/documentKinds'
import { isStudyPreset, QUERY_PRESET_OPTIONS } from '../constants/queryPresets'
import type {
  CourseStructureResponse,
  CourseStructureSubtopic,
  CourseStructureUnit,
  QueryPreset,
  StructurePreviewPart,
  StructurePreviewUnit,
  StudyLayoutResponse,
  StudyLayoutSource,
} from '../types'

export type StructureScopeKind = 'unit' | 'part' | 'subtopic'

export interface StructureScopeSelection {
  unitIds: Set<string>
  partIds: Set<string>
  subtopicIds: Set<string>
}

interface CourseStructurePanelProps {
  courseId: string
  layout: StudyLayoutResponse | null
  layoutLoading: boolean
  layoutError: string | null
  structure: CourseStructureResponse | null
  structureLoading: boolean
  structureError: string | null
  queryPreset: QueryPreset
  scopeSelection: StructureScopeSelection
  onScopeSelectionChange: (selection: StructureScopeSelection) => void
  onQueryPresetChange: (preset: QueryPreset) => void
  onReload: () => void
  onStructureSaved: () => void
}

const ASSIGNABLE_KINDS = new Set(['notes', 'textbook', 'syllabus'])

function formatDocKindLabel(docKind: string): string {
  const match = DOCUMENT_KIND_OPTIONS.find((option) => option.value === docKind)
  return match?.label ?? docKind
}

function isAssignableSource(source: StudyLayoutSource): boolean {
  return source.status === 'ready' && ASSIGNABLE_KINDS.has(source.doc_kind)
}

function clonePreviewUnits(units: StructurePreviewUnit[]): StructurePreviewUnit[] {
  return units.map((unit) => ({
    title: unit.title,
    parts: unit.parts?.map((part) => ({
      title: part.title,
      subtopics: [...part.subtopics],
    })),
    subtopics: unit.subtopics ? [...unit.subtopics] : undefined,
  }))
}

function countPreviewNodes(units: StructurePreviewUnit[]): number {
  return units.reduce((total, unit) => {
    if (unit.parts?.length) {
      return (
        total +
        1 +
        unit.parts.reduce((partTotal, part) => partTotal + 1 + part.subtopics.length, 0)
      )
    }
    return total + 1 + (unit.subtopics?.length ?? 0)
  }, 0)
}

function collectStructureIds(structure: CourseStructureResponse | null) {
  const unitIds: string[] = []
  const partIds: string[] = []
  const subtopicIds: string[] = []

  for (const unit of structure?.units ?? []) {
    unitIds.push(unit.id)
    if (unit.parts?.length) {
      for (const part of unit.parts) {
        partIds.push(part.id)
        for (const subtopic of part.subtopics) {
          subtopicIds.push(subtopic.id)
        }
      }
    } else {
      for (const subtopic of unit.subtopics ?? []) {
        subtopicIds.push(subtopic.id)
      }
    }
  }

  return { unitIds, partIds, subtopicIds }
}

interface DocumentAssignProps {
  nodeLabel: string
  documentIds: string[]
  assignableSources: StudyLayoutSource[]
  busyKey: string | null
  onToggle: (documentId: string, checked: boolean) => void
}

function DocumentAssignCheckboxes({
  nodeLabel,
  documentIds,
  assignableSources,
  busyKey,
  onToggle,
}: DocumentAssignProps) {
  if (assignableSources.length === 0) {
    return <p className="muted structure-doc-empty">No assignable PDFs yet.</p>
  }

  return (
    <ul className="structure-doc-list">
      {assignableSources.map((source) => {
        const checked = documentIds.includes(source.document_id)
        const busy = busyKey === source.document_id

        return (
          <li key={source.document_id} className="structure-doc-row">
            <label className="structure-doc-label">
              <input
                type="checkbox"
                className="source-checkbox"
                checked={checked}
                disabled={busy}
                aria-label={`Assign ${source.filename} to ${nodeLabel}`}
                onChange={(event) => onToggle(source.document_id, event.target.checked)}
              />
              <span className="structure-doc-name">{source.filename}</span>
              <span className={`source-doc-kind-badge source-doc-kind-${source.doc_kind}`}>
                {formatDocKindLabel(source.doc_kind)}
              </span>
            </label>
          </li>
        )
      })}
    </ul>
  )
}

interface ScopeToggleProps {
  kind: StructureScopeKind
  id: string
  label: string
  checked: boolean
  visible: boolean
  onToggle: (kind: StructureScopeKind, id: string, checked: boolean) => void
}

function ScopeToggle({ kind, id, label, checked, visible, onToggle }: ScopeToggleProps) {
  if (!visible) return null

  return (
    <label
      className="structure-scope-toggle"
      title="Include in query scope"
      onClick={(event) => event.stopPropagation()}
    >
      <input
        type="checkbox"
        className="source-checkbox"
        checked={checked}
        aria-label={`Scope queries to ${label}`}
        onChange={(event) => onToggle(kind, id, event.target.checked)}
      />
      <span className="sr-only">Scope</span>
    </label>
  )
}

export function CourseStructurePanel({
  courseId,
  layout,
  layoutLoading,
  layoutError,
  structure,
  structureLoading,
  structureError,
  queryPreset,
  scopeSelection,
  onScopeSelectionChange,
  onQueryPresetChange,
  onReload,
  onStructureSaved,
}: CourseStructurePanelProps) {
  const sources = layout?.sources ?? []
  const assignableSources = useMemo(
    () => sources.filter(isAssignableSource),
    [sources],
  )

  const [pasteText, setPasteText] = useState('')
  const [previewUnits, setPreviewUnits] = useState<StructurePreviewUnit[] | null>(null)
  const [showReplaceImport, setShowReplaceImport] = useState(false)
  const [parseWarning, setParseWarning] = useState<string | null>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const loading = layoutLoading || structureLoading
  const error = layoutError ?? structureError
  const showScope = isStudyPreset(queryPreset)
  const hasPersistedStructure = (structure?.units.length ?? 0) > 0
  const inPreviewMode = previewUnits !== null

  const studyPresetChips = useMemo(
    () => QUERY_PRESET_OPTIONS.filter((option) => isStudyPreset(option.value)),
    [],
  )

  const scopeCounts = useMemo(() => {
    const ids = collectStructureIds(structure)
    return {
      units: scopeSelection.unitIds.size,
      parts: scopeSelection.partIds.size,
      subtopics: scopeSelection.subtopicIds.size,
      totalUnits: ids.unitIds.length,
      totalParts: ids.partIds.length,
      totalSubtopics: ids.subtopicIds.length,
    }
  }, [scopeSelection, structure])

  const runAction = useCallback(
    async (label: string, action: () => Promise<void>) => {
      setBusyAction(label)
      setActionError(null)
      try {
        await action()
      } catch (err) {
        if (err instanceof CourseStructureApiError) {
          setActionError(`${err.status}: ${err.message}`)
        } else {
          setActionError(err instanceof Error ? err.message : 'Action failed')
        }
      } finally {
        setBusyAction(null)
      }
    },
    [],
  )

  const handleImportPaste = (event: FormEvent) => {
    event.preventDefault()
    const text = pasteText.trim()
    if (!text) return

    void runAction('import-paste', async () => {
      const response = await importStructurePaste(courseId, text)
      setPreviewUnits(clonePreviewUnits(response.units))
      setParseWarning(response.parse_warning ?? null)
    })
  }

  const handleImportSyllabus = () => {
    void runAction('import-syllabus', async () => {
      const response = await importStructureSyllabus(courseId)
      setPreviewUnits(clonePreviewUnits(response.units))
      setParseWarning(response.parse_warning ?? null)
      setPasteText('')
    })
  }

  const handleConfirmPreview = () => {
    if (!previewUnits?.length) return

    void runAction('confirm', async () => {
      await confirmCourseStructure(courseId, previewUnits)
      setPreviewUnits(null)
      setParseWarning(null)
      setPasteText('')
      onStructureSaved()
    })
  }

  const handleCancelPreview = () => {
    setPreviewUnits(null)
    setParseWarning(null)
  }

  const updatePreviewUnitTitle = (index: number, title: string) => {
    setPreviewUnits((prev) => {
      if (!prev) return prev
      const next = clonePreviewUnits(prev)
      next[index] = { ...next[index], title }
      return next
    })
  }

  const updatePreviewPartTitle = (unitIndex: number, partIndex: number, title: string) => {
    setPreviewUnits((prev) => {
      if (!prev) return prev
      const next = clonePreviewUnits(prev)
      const parts = next[unitIndex].parts
      if (!parts) return prev
      parts[partIndex] = { ...parts[partIndex], title }
      return next
    })
  }

  const updatePreviewSubtopicTitle = (
    unitIndex: number,
    partIndex: number | null,
    subtopicIndex: number,
    title: string,
  ) => {
    setPreviewUnits((prev) => {
      if (!prev) return prev
      const next = clonePreviewUnits(prev)
      if (partIndex === null) {
        const subtopics = next[unitIndex].subtopics
        if (!subtopics) return prev
        subtopics[subtopicIndex] = title
      } else {
        const parts = next[unitIndex].parts
        if (!parts) return prev
        parts[partIndex].subtopics[subtopicIndex] = title
      }
      return next
    })
  }

  const handleScopeToggle = (kind: StructureScopeKind, id: string, checked: boolean) => {
    const next: StructureScopeSelection = {
      unitIds: new Set(scopeSelection.unitIds),
      partIds: new Set(scopeSelection.partIds),
      subtopicIds: new Set(scopeSelection.subtopicIds),
    }

    const target =
      kind === 'unit' ? next.unitIds : kind === 'part' ? next.partIds : next.subtopicIds

    if (checked) {
      target.add(id)
    } else {
      target.delete(id)
    }

    onScopeSelectionChange(next)
  }

  const handleSelectAllScope = () => {
    const ids = collectStructureIds(structure)
    onScopeSelectionChange({
      unitIds: new Set(ids.unitIds),
      partIds: new Set(ids.partIds),
      subtopicIds: new Set(ids.subtopicIds),
    })
  }

  const handleClearScope = () => {
    onScopeSelectionChange({
      unitIds: new Set(),
      partIds: new Set(),
      subtopicIds: new Set(),
    })
  }

  const handleDocumentToggle = async (
    level: 'unit' | 'part' | 'subtopic',
    nodeId: string,
    currentIds: string[],
    documentId: string,
    checked: boolean,
  ) => {
    const nextIds = checked
      ? [...currentIds, documentId]
      : currentIds.filter((id) => id !== documentId)

    setBusyAction(`assign-${documentId}`)
    setActionError(null)
    try {
      if (level === 'unit') {
        await assignUnitDocuments(courseId, nodeId, nextIds)
      } else if (level === 'part') {
        await assignPartDocuments(courseId, nodeId, nextIds)
      } else {
        await assignSubtopicDocuments(courseId, nodeId, nextIds)
      }
      onStructureSaved()
    } catch (err) {
      if (err instanceof CourseStructureApiError) {
        setActionError(`${err.status}: ${err.message}`)
      } else {
        setActionError(err instanceof Error ? err.message : 'Could not assign document')
      }
    } finally {
      setBusyAction(null)
    }
  }

  const renderPreviewTree = () => {
    if (!previewUnits) return null

    return (
      <section className="structure-preview-panel">
        <h3>Preview — edit before saving</h3>
        {parseWarning && (
          <p className="structure-parse-warning muted" role="status">
            {parseWarning}
          </p>
        )}
        <p className="muted">
          {previewUnits.length} units · {countPreviewNodes(previewUnits)} nodes
        </p>

        <ul className="structure-tree structure-preview-tree">
          {previewUnits.map((unit, unitIndex) => (
            <li key={`preview-unit-${unitIndex}`} className="structure-unit-row">
              <details open className="structure-details">
                <summary className="structure-summary">
                  <input
                    type="text"
                    className="structure-title-input"
                    value={unit.title}
                    aria-label="Unit title"
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => updatePreviewUnitTitle(unitIndex, event.target.value)}
                  />
                </summary>

                {unit.parts?.map((part: StructurePreviewPart, partIndex: number) => (
                  <details key={`preview-part-${unitIndex}-${partIndex}`} className="structure-part-details">
                    <summary className="structure-part-summary">
                      <input
                        type="text"
                        className="structure-title-input"
                        value={part.title}
                        aria-label="Part title"
                        onClick={(event) => event.stopPropagation()}
                        onChange={(event) =>
                          updatePreviewPartTitle(unitIndex, partIndex, event.target.value)
                        }
                      />
                    </summary>
                    <ul className="structure-subtopic-list">
                      {part.subtopics.map((subtopic, subtopicIndex) => (
                        <li key={`preview-sub-${unitIndex}-${partIndex}-${subtopicIndex}`}>
                          <input
                            type="text"
                            className="structure-title-input structure-subtopic-input"
                            value={subtopic}
                            aria-label="Subtopic title"
                            onChange={(event) =>
                              updatePreviewSubtopicTitle(
                                unitIndex,
                                partIndex,
                                subtopicIndex,
                                event.target.value,
                              )
                            }
                          />
                        </li>
                      ))}
                    </ul>
                  </details>
                ))}

                {unit.subtopics?.length ? (
                  <ul className="structure-subtopic-list">
                    {unit.subtopics.map((subtopic, subtopicIndex) => (
                      <li key={`preview-sub-${unitIndex}-${subtopicIndex}`}>
                        <input
                          type="text"
                          className="structure-title-input structure-subtopic-input"
                          value={subtopic}
                          aria-label="Subtopic title"
                          onChange={(event) =>
                            updatePreviewSubtopicTitle(
                              unitIndex,
                              null,
                              subtopicIndex,
                              event.target.value,
                            )
                          }
                        />
                      </li>
                    ))}
                  </ul>
                ) : null}
              </details>
            </li>
          ))}
        </ul>

        <div className="structure-preview-actions">
          <button
            type="button"
            className="submit-btn"
            disabled={busyAction === 'confirm' || previewUnits.length === 0}
            onClick={handleConfirmPreview}
          >
            {busyAction === 'confirm' ? 'Saving…' : 'Confirm & save'}
          </button>
          <button type="button" className="text-btn" onClick={handleCancelPreview}>
            Cancel
          </button>
        </div>
      </section>
    )
  }

  const renderPersistedSubtopic = (subtopic: CourseStructureSubtopic) => (
    <li key={subtopic.id} className="structure-subtopic-row">
      <details className="structure-subtopic-details">
        <summary className="structure-subtopic-summary">
          <ScopeToggle
            kind="subtopic"
            id={subtopic.id}
            label={subtopic.title}
            checked={scopeSelection.subtopicIds.has(subtopic.id)}
            visible={showScope}
            onToggle={handleScopeToggle}
          />
          <span className="structure-node-title">{subtopic.title}</span>
          <span className="structure-doc-count muted">
            {subtopic.document_ids.length} PDF{subtopic.document_ids.length === 1 ? '' : 's'}
          </span>
        </summary>
        <DocumentAssignCheckboxes
          nodeLabel={subtopic.title}
          documentIds={subtopic.document_ids}
          assignableSources={assignableSources}
          busyKey={busyAction?.startsWith('assign-') ? busyAction.slice(7) : null}
          onToggle={(documentId, checked) =>
            void handleDocumentToggle(
              'subtopic',
              subtopic.id,
              subtopic.document_ids,
              documentId,
              checked,
            )
          }
        />
      </details>
    </li>
  )

  const renderPersistedUnit = (unit: CourseStructureUnit) => (
    <li key={unit.id} className="structure-unit-row card-hover">
      <details className="structure-details">
        <summary className="structure-summary">
          <ScopeToggle
            kind="unit"
            id={unit.id}
            label={unit.title}
            checked={scopeSelection.unitIds.has(unit.id)}
            visible={showScope}
            onToggle={handleScopeToggle}
          />
          <span className="structure-node-title">{unit.title}</span>
          <span className="structure-doc-count muted">
            {unit.document_ids.length} PDF{unit.document_ids.length === 1 ? '' : 's'}
          </span>
        </summary>

        <DocumentAssignCheckboxes
          nodeLabel={unit.title}
          documentIds={unit.document_ids}
          assignableSources={assignableSources}
          busyKey={busyAction?.startsWith('assign-') ? busyAction.slice(7) : null}
          onToggle={(documentId, checked) =>
            void handleDocumentToggle('unit', unit.id, unit.document_ids, documentId, checked)
          }
        />

        {unit.parts?.map((part) => (
          <details key={part.id} className="structure-part-details">
            <summary className="structure-part-summary">
              <ScopeToggle
                kind="part"
                id={part.id}
                label={part.title}
                checked={scopeSelection.partIds.has(part.id)}
                visible={showScope}
                onToggle={handleScopeToggle}
              />
              <span className="structure-node-title">{part.title}</span>
              <span className="structure-doc-count muted">
                {part.document_ids.length} PDF{part.document_ids.length === 1 ? '' : 's'}
              </span>
            </summary>

            <DocumentAssignCheckboxes
              nodeLabel={part.title}
              documentIds={part.document_ids}
              assignableSources={assignableSources}
              busyKey={busyAction?.startsWith('assign-') ? busyAction.slice(7) : null}
              onToggle={(documentId, checked) =>
                void handleDocumentToggle('part', part.id, part.document_ids, documentId, checked)
              }
            />

            <ul className="structure-subtopic-list">
              {part.subtopics.map((subtopic) => renderPersistedSubtopic(subtopic))}
            </ul>
          </details>
        ))}

        {!unit.parts?.length && unit.subtopics && (
          <ul className="structure-subtopic-list">
            {unit.subtopics.map((subtopic) => renderPersistedSubtopic(subtopic))}
          </ul>
        )}
      </details>
    </li>
  )

  return (
    <section className="panel course-structure-panel" aria-live="polite">
      <div className="sources-panel-header">
        <div>
          <div className="sources-panel-title-row">
            <h2>Course structure</h2>
            <span className="organized-study-badge" role="status">
              Organized Study
            </span>
          </div>
          <p className="panel-intro">
            Import units from your syllabus, assign PDFs, and scope study queries to units or
            subtopics.
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
          Loading course structure…
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

      {!loading && !error && (
        <>
          <div className="structure-preset-chips preset-tabs" role="group" aria-label="Study presets">
            {studyPresetChips.map((option) => (
              <button
                key={option.value}
                type="button"
                className={['preset-tab', queryPreset === option.value ? 'is-active' : '']
                  .filter(Boolean)
                  .join(' ')}
                aria-pressed={queryPreset === option.value}
                onClick={() => onQueryPresetChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          {showScope && hasPersistedStructure && !inPreviewMode && (
            <div className="sources-selection-toolbar">
              <p className="sources-selection-count" role="status">
                Scope: {scopeCounts.units}/{scopeCounts.totalUnits} units,{' '}
                {scopeCounts.parts}/{scopeCounts.totalParts} parts,{' '}
                {scopeCounts.subtopics}/{scopeCounts.totalSubtopics} subtopics
              </p>
              <div className="sources-selection-actions">
                <button type="button" className="text-btn" onClick={handleSelectAllScope}>
                  Select all
                </button>
                <button type="button" className="text-btn" onClick={handleClearScope}>
                  Clear
                </button>
              </div>
            </div>
          )}

          {!inPreviewMode && !hasPersistedStructure && (
            <div className="structure-import-panel">
              <p className="muted">No course structure yet for {courseId}.</p>
              <form className="structure-paste-form" onSubmit={handleImportPaste}>
                <label className="field">
                  <span>Paste unit outline</span>
                  <textarea
                    value={pasteText}
                    onChange={(event) => setPasteText(event.target.value)}
                    rows={6}
                    placeholder={'Unit 1 Introduction\n  Part A Basics\n    Topic one, topic two\nUnit 2 Advanced'}
                    disabled={busyAction === 'import-paste'}
                  />
                </label>
                <div className="structure-import-actions">
                  <button
                    type="submit"
                    className="text-btn"
                    disabled={!pasteText.trim() || busyAction === 'import-paste'}
                  >
                    {busyAction === 'import-paste' ? 'Parsing…' : 'Preview paste'}
                  </button>
                  <button
                    type="button"
                    className="submit-btn structure-syllabus-btn"
                    disabled={busyAction === 'import-syllabus'}
                    onClick={handleImportSyllabus}
                  >
                    {busyAction === 'import-syllabus'
                      ? 'Importing…'
                      : 'Import from syllabus PDF'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {!inPreviewMode && hasPersistedStructure && (
            <>
              <ul className="structure-tree">{structure!.units.map(renderPersistedUnit)}</ul>

              <div className="structure-import-panel structure-import-secondary">
                <button
                  type="button"
                  className="text-btn"
                  onClick={() => setShowReplaceImport((open) => !open)}
                >
                  {showReplaceImport ? 'Hide paste import' : 'Replace via paste'}
                </button>
                <button
                  type="button"
                  className="text-btn"
                  disabled={busyAction === 'import-syllabus'}
                  onClick={handleImportSyllabus}
                >
                  {busyAction === 'import-syllabus' ? 'Importing…' : 'Re-import from syllabus'}
                </button>
              </div>

              {showReplaceImport && (
                <form className="structure-paste-form" onSubmit={handleImportPaste}>
                  <label className="field">
                    <span>Paste replacement outline</span>
                    <textarea
                      value={pasteText}
                      onChange={(event) => setPasteText(event.target.value)}
                      rows={5}
                      disabled={busyAction === 'import-paste'}
                    />
                  </label>
                  <button
                    type="submit"
                    className="text-btn"
                    disabled={!pasteText.trim() || busyAction === 'import-paste'}
                  >
                    {busyAction === 'import-paste' ? 'Parsing…' : 'Preview paste'}
                  </button>
                </form>
              )}
            </>
          )}

          {inPreviewMode && renderPreviewTree()}

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
