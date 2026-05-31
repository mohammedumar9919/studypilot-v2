import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'

import { postDocumentUpload, UploadApiError } from '../api/uploadClient'
import { DOCUMENT_KIND_OPTIONS } from '../constants/documentKinds'
import type { DocumentKind, DocumentUploadResponse, UploadPanelPhase } from '../types'

interface DocumentUploadPanelProps {
  courseId: string
  disabled?: boolean
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
  onUploadStart,
  onUploadSuccess,
  onPhaseChange,
}: DocumentUploadPanelProps) {
  const [docKind, setDocKind] = useState<DocumentKind>('notes')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [phase, setPhase] = useState<UploadPanelPhase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<DocumentUploadResponse | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [elapsedMs, setElapsedMs] = useState(0)

  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<number | null>(null)
  const startRef = useRef(0)
  const inputRef = useRef<HTMLInputElement>(null)

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
    const trimmedCourse = courseId.trim()
    if (!trimmedCourse || !selectedFile || phase === 'indexing') return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setError(null)
    setSuccess(null)
    setPanelPhase('indexing')
    onUploadStart?.()
    startRef.current = Date.now()
    setElapsedMs(0)
    clearTimer()
    timerRef.current = window.setInterval(() => {
      setElapsedMs(Date.now() - startRef.current)
    }, 250)

    void postDocumentUpload(trimmedCourse, selectedFile, docKind, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setSuccess(response)
        setPanelPhase('success')
        onUploadSuccess?.(response)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof UploadApiError) {
          setError(`${err.status}: ${err.message}`)
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
  const canSubmit = Boolean(selectedFile && courseId.trim()) && !isIndexing && !disabled

  return (
    <section className="panel document-upload-panel glass-panel">
      <div className="document-upload-header">
        <div>
          <h2>Upload course PDF</h2>
          <p className="panel-intro">
            PDF only. Indexing runs on your machine — typically 30–60 seconds. No fake progress
            bars.
          </p>
        </div>
      </div>

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
          Course: {courseId.trim() || '—'} · Re-upload replaces same filename + type
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
            <span className="gradient-accent">Indexing</span>…
          </span>
          <span className="progress-elapsed">{formatElapsed(elapsedMs)}</span>
        </div>
      )}

      {phase === 'success' && success && (
        <div className="upload-success-card" role="status">
          <h3>Ready to study</h3>
          <p>
            <strong>{success.filename}</strong> indexed — {success.page_count} pages (
            {success.doc_kind}).
          </p>
          {success.extraction_quality?.outline?.unit_count != null && (
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
