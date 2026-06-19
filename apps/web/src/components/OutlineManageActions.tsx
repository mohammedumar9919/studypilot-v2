import { useRef, useState, type ChangeEvent } from 'react'

import { OutlineApiError, postCourseOutline, rebuildCourseOutline } from '../api/outlineClient'
import type { OutlineQuality, OutlineSource, OutlineUnit, OutlineUploadPayload } from '../types'
import { canManageOutline, canRebuildOutline } from '../utils/courseLabels'

interface OutlineManageActionsProps {
  courseId: string
  outlineSource?: OutlineSource
  outlineQuality?: OutlineQuality
  disabled?: boolean
  prominent?: boolean
  uploadButtonLabel?: string
  onSuccess: () => void
}

export function OutlineManageActions({
  courseId,
  outlineSource,
  outlineQuality,
  disabled = false,
  prominent = false,
  uploadButtonLabel = 'Upload outline',
  onSuccess,
}: OutlineManageActionsProps) {
  const [uploadOpen, setUploadOpen] = useState(prominent)
  const [busy, setBusy] = useState<'upload' | 'rebuild' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  if (!canManageOutline(outlineSource)) return null

  const showProminent = prominent || outlineQuality === 'low'

  const handleRebuild = () => {
    if (disabled || busy) return
    setActionError(null)
    setBusy('rebuild')
    void rebuildCourseOutline(courseId.trim())
      .then(() => onSuccess())
      .catch((err) => {
        setActionError(err instanceof OutlineApiError ? `${err.status}: ${err.message}` : 'Re-extract failed')
      })
      .finally(() => setBusy(null))
  }

  const handleFileUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || disabled || busy) return

    setActionError(null)
    setBusy('upload')

    void file
      .text()
      .then((raw) => JSON.parse(raw) as OutlineUploadPayload)
      .then((payload) => postCourseOutline(courseId.trim(), payload))
      .then(() => {
        setUploadOpen(showProminent)
        onSuccess()
      })
      .catch((err) => {
        if (err instanceof OutlineApiError) {
          setActionError(`${err.status}: ${err.message}`)
        } else if (err instanceof SyntaxError) {
          setActionError('Invalid JSON file — check the outline format.')
        } else {
          setActionError(err instanceof Error ? err.message : 'Upload failed')
        }
      })
      .finally(() => {
        setBusy(null)
        if (fileRef.current) fileRef.current.value = ''
      })
  }

  const openUploadPicker = () => {
    if (disabled || busy) return
    fileRef.current?.click()
  }

  return (
    <div className={`outline-manage-actions ${showProminent ? 'is-prominent' : ''}`}>
      <div className="outline-manage-buttons">
        {canRebuildOutline(outlineSource) && (
          <button
            type="button"
            className={showProminent ? 'submit-btn outline-action-btn' : 'text-btn outline-rebuild-btn'}
            disabled={disabled || busy !== null}
            onClick={handleRebuild}
          >
            {busy === 'rebuild' ? 'Re-extracting…' : 'Re-extract TOC'}
          </button>
        )}
        {showProminent ? (
          <>
            <button
              type="button"
              className="submit-btn outline-action-btn outline-action-secondary"
              disabled={disabled || busy !== null}
              onClick={openUploadPicker}
            >
              {busy === 'upload' ? 'Uploading…' : uploadButtonLabel}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="outline-upload-input sr-only"
              disabled={disabled || busy !== null}
              onChange={handleFileUpload}
            />
          </>
        ) : (
          <button
            type="button"
            className="text-btn"
            disabled={disabled || busy !== null}
            aria-expanded={uploadOpen}
            onClick={() => setUploadOpen((open) => !open)}
          >
            {uploadOpen ? 'Cancel upload' : uploadButtonLabel}
          </button>
        )}
      </div>

      {!showProminent && uploadOpen && (
        <div className="outline-upload-panel">
          <p className="muted outline-upload-hint">
            Choose a JSON file matching the course outline shape (units with sections).
          </p>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="outline-upload-input"
            disabled={disabled || busy !== null}
            onChange={handleFileUpload}
          />
          {busy === 'upload' && (
            <p className="muted" role="status">
              Uploading outline…
            </p>
          )}
        </div>
      )}

      {showProminent && uploadOpen && (
        <p className="muted outline-upload-hint">
          JSON outline upload — same format as the API outline endpoint.
        </p>
      )}

      {actionError && (
        <p className="outline-action-error" role="alert">
          {actionError}
        </p>
      )}
    </div>
  )
}

interface OutlineConfirmPanelProps {
  courseId: string
  units: OutlineUnit[]
  outlineSource?: OutlineSource
  onDismiss: () => void
  onSuccess: () => void
}

export function OutlineConfirmPanel({
  courseId,
  units,
  outlineSource,
  onDismiss,
  onSuccess,
}: OutlineConfirmPanelProps) {
  const chapterCount = units.length
  const chapterLabel = chapterCount === 1 ? 'chapter' : 'chapters'

  return (
    <section className="outline-confirm-panel" role="dialog" aria-labelledby="outline-confirm-title">
      <h3 id="outline-confirm-title">Check your course outline</h3>
      <p className="outline-confirm-intro">
        We detected {chapterCount} {chapterLabel} from your PDF. Does this look right?
      </p>

      <ul className="outline-confirm-units">
        {units.map((unit) => (
          <li key={unit.id}>{unit.title}</li>
        ))}
      </ul>

      <div className="outline-confirm-actions">
        <button type="button" className="submit-btn" onClick={onDismiss}>
          Looks good
        </button>
        <OutlineManageActions
          courseId={courseId}
          outlineSource={outlineSource}
          outlineQuality="low"
          prominent
          uploadButtonLabel="Upload corrected outline"
          onSuccess={onSuccess}
        />
      </div>
    </section>
  )
}
