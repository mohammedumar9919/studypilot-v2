import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'

import {
  enrichUploadAfterIngest,
  IngestPollError,
  isAsyncQueuedUpload,
  pollIngestStatusUntilDone,
} from '../api/ingestStatusClient'
import { postDocumentUpload, uploadTimeoutMinutes, UploadApiError } from '../api/uploadClient'
import { DOCUMENT_KIND_OPTIONS } from '../constants/documentKinds'
import {
  resolveUploadIntent,
  showsUploadIntentPicker,
  UPLOAD_INTENT_OPTIONS,
  type SelectableUploadIntent,
} from '../constants/uploadIntents'
import type { DocumentKind, DocumentUploadResponse, UploadPanelPhase } from '../types'

interface DocumentUploadPanelProps {
  courseId: string
  disabled?: boolean
  onCourseIdCommit: (value: string) => void
  onUploadStart?: () => void
  onUploadSuccess?: (response: DocumentUploadResponse) => void
  onPhaseChange?: (phase: UploadPanelPhase) => void
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return minutes > 0
    ? `${minutes}:${seconds.toString().padStart(2, '0')}`
    : `${seconds}s`
}

export function DocumentUploadPanel({
  courseId,
  disabled = false,
  onCourseIdCommit,
  onUploadStart,
  onUploadSuccess,
  onPhaseChange,
}: DocumentUploadPanelProps) {
  const [draftCourseId, setDraftCourseId] = useState(courseId)
  const [docKind, setDocKind] = useState<DocumentKind>('notes')
  const [uploadIntentChoice, setUploadIntentChoice] = useState<SelectableUploadIntent>('quick')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [phase, setPhase] = useState<UploadPanelPhase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<DocumentUploadResponse | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [ingestProgress, setIngestProgress] = useState<number | null>(null)
  const [ingestStatusLabel, setIngestStatusLabel] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<number | null>(null)
  const startRef = useRef(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraftCourseId(courseId)
  }, [courseId])

  const commitCourseId = useCallback(() => {
    const trimmed = draftCourseId.trim()
    if (trimmed !== courseId.trim()) {
      onCourseIdCommit(trimmed)
    }
  }, [courseId, draftCourseId, onCourseIdCommit])

  const setPanelPhase = useCallback(
    (next: UploadPanelPhase) => {
      setPhase(next)
      onPhaseChange?.(next)
    },
    [onPhaseChange],
  )

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(
    () => () => {
      abortRef.current?.abort()
      clearTimer()
    },
    [clearTimer],
  )

  const pickPdf = (file: File | null) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF uploads are supported.')
      setPanelPhase('error')
      return
    }
    setSelectedFile(file)
    setError(null)
    if (phase === 'error') setPanelPhase('idle')
  }

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    pickPdf(event.target.files?.[0] ?? null)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragActive(false)
    if (disabled || phase === 'indexing') return
    pickPdf(event.dataTransfer.files?.[0] ?? null)
  }

  const handleUpload = () => {
    const trimmedCourse = draftCourseId.trim()
    if (!trimmedCourse) {
      setError('Enter a course name or code before uploading.')
      setPanelPhase('error')
      return
    }
    if (trimmedCourse !== courseId.trim()) {
      onCourseIdCommit(trimmedCourse)
    }
    if (!selectedFile || phase === 'indexing') return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setError(null)
    setSuccess(null)
    setIngestProgress(null)
    setIngestStatusLabel(null)
    setPanelPhase('indexing')
    onUploadStart?.()
    startRef.current = Date.now()
    setElapsedMs(0)
    clearTimer()
    timerRef.current = window.setInterval(() => {
      setElapsedMs(Date.now() - startRef.current)
    }, 250)

    const uploadIntent = resolveUploadIntent(docKind, uploadIntentChoice)
    void postDocumentUpload(trimmedCourse, selectedFile, docKind, uploadIntent, controller.signal)
      .then(async (response) => {
        if (controller.signal.aborted) return

        let readyResponse = response
        if (isAsyncQueuedUpload(response)) {
          setIngestStatusLabel('Queued')
          setIngestProgress(response.status === 'queued' ? 0 : null)
          await pollIngestStatusUntilDone(response.document_id, docKind, {
            signal: controller.signal,
            onUpdate: (status) => {
              if (controller.signal.aborted) return
              setIngestProgress(status.progress_pct)
              if (status.status === 'queued') {
                setIngestStatusLabel('Queued')
              } else if (status.status === 'processing' || status.document_status === 'processing') {
                setIngestStatusLabel('Processing')
              } else {
                setIngestStatusLabel('Indexing')
              }
            },
          })
          readyResponse = await enrichUploadAfterIngest(response, controller.signal)
        }

        if (controller.signal.aborted) return
        setSuccess(readyResponse)
        setPanelPhase('success')
        onUploadSuccess?.(readyResponse)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof UploadApiError) {
          setError(`${err.status}: ${err.message}`)
        } else if (err instanceof IngestPollError) {
          setError(err.message)
        } else {
          setError(err instanceof Error ? err.message : 'Upload failed')
        }
        setPanelPhase('error')
      })
      .finally(() => {
        clearTimer()
        abortRef.current = null
      })
  }

  const isIndexing = phase === 'indexing'
  const canSubmit = Boolean(selectedFile && draftCourseId.trim()) && !isIndexing && !disabled
  const timeoutMinutes = uploadTimeoutMinutes(docKind)
  const indexingHint =
    ingestStatusLabel === 'Queued'
      ? 'Upload received — waiting for the ingest worker. Keep this tab open until indexing finishes.'
      : docKind === 'past_paper'
        ? 'Past papers may run OCR — often 5–15+ minutes on first upload. Keep this tab open.'
        : 'Large notes can take several minutes on first upload (embed model load). Keep this tab open.'
  const indexingTitle = ingestStatusLabel ?? 'Indexing'

  return (
    <section className="panel document-upload-panel glass-panel">
      <div className="document-upload-header">
        <div>
          <h2>Upload course PDF</h2>
          <p className="panel-intro">
            PDF only. Upload returns quickly when background indexing is enabled; otherwise
            indexing blocks until done — notes often 1–10 min, past papers longer with OCR (up to{' '}
            {timeoutMinutes} min before timeout).
          </p>
        </div>
      </div>

      <label className="field">
        <span>Course name / code</span>
        <input
          type="text"
          value={draftCourseId}
          onChange={(event) => setDraftCourseId(event.target.value)}
          onBlur={commitCourseId}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              commitCourseId()
            }
          }}
          disabled={disabled || isIndexing}
          placeholder="PPL, CHEM201"
          autoComplete="off"
        />
      </label>

      <label className="field">
        <span>Document type</span>
        <select
          value={docKind}
          disabled={disabled || isIndexing}
          onChange={(event) => setDocKind(event.target.value as DocumentKind)}
        >
          {DOCUMENT_KIND_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {showsUploadIntentPicker(docKind) && (
        <fieldset className="field upload-intent-field">
          <legend>Study layout</legend>
          <div className="upload-intent-options">
            {UPLOAD_INTENT_OPTIONS.map((option) => (
              <label key={option.value} className="upload-intent-option">
                <input
                  type="radio"
                  name="upload-intent"
                  value={option.value}
                  checked={uploadIntentChoice === option.value}
                  disabled={disabled || isIndexing}
                  onChange={() => setUploadIntentChoice(option.value)}
                />
                <span className="upload-intent-option-body">
                  <span className="upload-intent-option-label">{option.label}</span>
                  <span className="upload-intent-option-helper muted">{option.helper}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <div
        className={[
          'upload-dropzone',
          dragActive ? 'is-drag-active' : '',
          selectedFile ? 'has-file' : '',
          isIndexing ? 'is-indexing' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled && !isIndexing) setDragActive(true)
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="upload-file-input"
          disabled={disabled || isIndexing}
          onChange={handleFileInput}
        />
        <p className="upload-dropzone-title">
          {selectedFile ? selectedFile.name : 'Drop a PDF here or choose a file'}
        </p>
        <p className="upload-dropzone-hint muted">
          Course: {draftCourseId.trim() || '—'} · Re-upload replaces same filename + type
        </p>
        <button
          type="button"
          className="upload-picker-btn"
          disabled={disabled || isIndexing}
          onClick={() => inputRef.current?.click()}
        >
          Choose PDF
        </button>
      </div>

      {isIndexing && (
        <div className="stage-pill upload-stage-pill" aria-live="polite">
          <span className="stage-pill-dot" aria-hidden="true" />
          <span className="stage-pill-label">
            <span className="gradient-accent">{indexingTitle}</span>…
          </span>
          <span className="progress-elapsed">{formatElapsed(elapsedMs)}</span>
          {ingestProgress !== null && (
            <div className="upload-progress-track" role="progressbar" aria-valuenow={ingestProgress} aria-valuemin={0} aria-valuemax={100}>
              <div className="upload-progress-fill" style={{ width: `${ingestProgress}%` }} />
            </div>
          )}
          <p className="upload-indexing-hint muted">{indexingHint}</p>
        </div>
      )}

      {phase === 'success' && success && (
        <div className="upload-success-card" role="status">
          <h3>Ready to study</h3>
          <p>
            <strong>{success.filename}</strong> indexed
            {success.page_count != null ? ` — ${success.page_count} pages` : ''} ({success.doc_kind}
            ).
          </p>
          <p className="muted">
            Course: <strong>{success.course_id}</strong>
          </p>
          {(success.upload_intent ?? success.extraction_quality?.upload_intent) === 'syllabus' &&
            success.extraction_quality?.outline?.unit_count != null && (
              <p className="muted">
                Outline detected: {success.extraction_quality.outline.unit_count} units
              </p>
            )}
        </div>
      )}

      {phase === 'error' && error && (
        <div className="upload-error-card" role="alert">
          <p>{error}</p>
        </div>
      )}

      <button
        type="button"
        className="submit-btn upload-submit-btn"
        disabled={!canSubmit}
        onClick={handleUpload}
      >
        {isIndexing ? (
          <>
            <span className="spinner spinner-inline" aria-hidden="true" />
            Indexing…
          </>
        ) : (
          <>
            Upload &amp; index
            <span className="submit-arrow" aria-hidden="true">
              →
            </span>
          </>
        )}
      </button>
    </section>
  )
}
