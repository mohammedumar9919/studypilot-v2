import { useRef, useState, type ChangeEvent } from 'react'

import {
  courseMapIneligibilityMessage,
  formatCourseMapPreviewLines,
  isCourseMapPromoteExtractionFailure,
  isOutlinePreviewNotReady,
} from '../api/courseMapClient'
import { OutlineApiError, postCourseOutline } from '../api/outlineClient'
import type { CourseMapEligibilityResponse, OutlineUploadPayload } from '../types'

interface CourseMapPromotionPanelProps {
  courseId: string
  eligibility: CourseMapEligibilityResponse | null
  loading: boolean
  error: string | null
  promoting: boolean
  promoteError: string | null
  onPromote: () => void
  onReload: () => void
}

function CourseMapPreviewBlock({
  syllabusFilename,
  preview,
}: {
  syllabusFilename: string | null | undefined
  preview: CourseMapEligibilityResponse['outline_preview']
}) {
  if (!preview || preview.unit_count <= 0) return null

  const filename = syllabusFilename ?? 'your syllabus PDF'
  const { visibleTitles, remainingCount } = formatCourseMapPreviewLines(preview)

  return (
    <div className="course-map-preview" role="status">
      <p className="course-map-preview-intro">
        We found {preview.unit_count} unit{preview.unit_count === 1 ? '' : 's'} in{' '}
        <strong>{filename}</strong>:
      </p>
      {visibleTitles.length > 0 && (
        <ul className="course-map-preview-units">
          {visibleTitles.map((title) => (
            <li key={title}>{title}</li>
          ))}
        </ul>
      )}
      {remainingCount > 0 && (
        <p className="muted course-map-preview-more">and {remainingCount} more</p>
      )}
    </div>
  )
}

function CourseMapOutlineUpload({
  courseId,
  disabled,
  onSuccess,
}: {
  courseId: string
  disabled?: boolean
  onSuccess: () => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const handleFileUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || disabled || busy) return

    setUploadError(null)
    setBusy(true)

    void file
      .text()
      .then((raw) => JSON.parse(raw) as OutlineUploadPayload)
      .then((payload) => postCourseOutline(courseId.trim(), payload))
      .then(() => onSuccess())
      .catch((err) => {
        if (err instanceof OutlineApiError) {
          setUploadError(`${err.status}: ${err.message}`)
        } else if (err instanceof SyntaxError) {
          setUploadError('Invalid JSON file — check the outline format.')
        } else {
          setUploadError(err instanceof Error ? err.message : 'Upload failed')
        }
      })
      .finally(() => {
        setBusy(false)
        if (fileRef.current) fileRef.current.value = ''
      })
  }

  return (
    <div className="course-map-outline-upload">
      <button
        type="button"
        className="submit-btn outline-action-btn outline-action-secondary"
        disabled={disabled || busy}
        onClick={() => fileRef.current?.click()}
      >
        {busy ? 'Uploading outline…' : 'Upload outline (JSON)'}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="application/json,.json"
        className="outline-upload-input sr-only"
        disabled={disabled || busy}
        onChange={handleFileUpload}
      />
      <p className="muted outline-upload-hint">
        JSON outline upload — same format as the API outline endpoint.
      </p>
      {uploadError && (
        <p className="outline-action-error" role="alert">
          {uploadError}
        </p>
      )}
    </div>
  )
}

export function CourseMapPromotionPanel({
  courseId,
  eligibility,
  loading,
  error,
  promoting,
  promoteError,
  onPromote,
  onReload,
}: CourseMapPromotionPanelProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)

  if (loading) {
    return (
      <div className="sources-panel-loading">
        <span className="spinner" aria-hidden="true" />
        Checking Course Map eligibility…
      </div>
    )
  }

  if (error) {
    return (
      <div className="sources-panel-alert alert-error" role="alert">
        <p>{error}</p>
        <button type="button" className="text-btn" onClick={onReload}>
          Retry
        </button>
      </div>
    )
  }

  if (!eligibility) {
    return (
      <div className="course-map-panel-empty" role="status">
        <p>Course Map status is unavailable for {courseId}.</p>
        <p className="muted">Upload at least one PDF, then try again.</p>
      </div>
    )
  }

  if (eligibility.eligible) {
    const outlineNotReady = isOutlinePreviewNotReady(eligibility.outline_preview)
    const showOutlineUpload =
      outlineNotReady || isCourseMapPromoteExtractionFailure(promoteError) || Boolean(promoteError)

    return (
      <div className="course-map-promotion-panel">
        <h3>Enable Course Map</h3>
        <p className="panel-intro">
          Promote this course to a unit sidebar and exam heatmap — like Chemistry or PPL.
        </p>

        <CourseMapPreviewBlock
          syllabusFilename={eligibility.syllabus_filename}
          preview={eligibility.outline_preview}
        />

        {eligibility.outline_quality && (
          <p className="muted course-map-promotion-meta">
            Outline quality: <strong>{eligibility.outline_quality}</strong>
          </p>
        )}

        {outlineNotReady ? (
          <div className="course-map-not-ready" role="status">
            <p>
              Outline not ready — re-upload syllabus with <strong>Syllabus / course map</strong>{' '}
              intent
            </p>
          </div>
        ) : !confirmOpen ? (
          <button
            type="button"
            className="submit-btn course-map-promote-btn"
            disabled={promoting}
            onClick={() => setConfirmOpen(true)}
          >
            Enable course map
          </button>
        ) : (
          <div
            className="course-map-confirm-panel"
            role="dialog"
            aria-labelledby="course-map-confirm-title"
          >
            <h4 id="course-map-confirm-title">Promote to Course Map?</h4>
            <CourseMapPreviewBlock
              syllabusFilename={eligibility.syllabus_filename}
              preview={eligibility.outline_preview}
            />
            <p className="muted">
              Your sidebar will switch to a unit tree and topic heatmap. You can still query all
              ingested PDFs.
            </p>
            <div className="course-map-confirm-actions">
              <button
                type="button"
                className="text-btn"
                disabled={promoting}
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="submit-btn"
                disabled={promoting}
                onClick={() => {
                  setConfirmOpen(false)
                  onPromote()
                }}
              >
                {promoting ? 'Promoting…' : 'Confirm promotion'}
              </button>
            </div>
          </div>
        )}

        {promoteError && (
          <div className="sources-panel-alert alert-error" role="alert">
            <p>{promoteError}</p>
          </div>
        )}

        {showOutlineUpload && (
          <CourseMapOutlineUpload courseId={courseId} disabled={promoting} onSuccess={onReload} />
        )}
      </div>
    )
  }

  return (
    <div className="course-map-promotion-panel course-map-ineligible" role="status">
      <h3>Course Map not ready</h3>
      <p>{courseMapIneligibilityMessage(eligibility.reason)}</p>
      {eligibility.reason === 'no_syllabus_document' && (
        <p className="muted">
          Upload your course syllabus PDF with <strong>Syllabus / course map</strong> intent in the
          upload panel.
        </p>
      )}
      {eligibility.reason === 'no_outline' && (
        <p className="muted">
          Re-upload with <strong>Syllabus / course map</strong> intent, or ingest a PDF with a clear
          table of contents.
        </p>
      )}
      {eligibility.reason === 'outline_quality_not_high' && (
        <p className="muted">
          Quick Study uploads skip outline extraction. Use syllabus intent or upload a clearer unit
          structure.
        </p>
      )}
      <CourseMapOutlineUpload courseId={courseId} onSuccess={onReload} />
    </div>
  )
}
