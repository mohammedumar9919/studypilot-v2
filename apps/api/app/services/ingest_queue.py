"""Postgres-backed ingest job queue (SP-013a)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Document, IngestJob
from app.services.ingestion import ingest_document, ingest_document_fast

INGEST_JOB_STATUSES = frozenset({"queued", "processing", "completed", "failed"})
INGEST_JOB_PHASES = frozenset({"fast", "heavy", "full"})
ACTIVE_JOB_STATUSES = frozenset({"queued", "processing"})


def is_ingest_async_enabled() -> bool:
    return os.environ.get("STUDYPILOT_INGEST_ASYNC", "0").strip().lower() in ("1", "true", "yes")


def enqueue_ingest_job(
    session: Session,
    *,
    document_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    phase: str = "full",
) -> IngestJob:
    if phase not in INGEST_JOB_PHASES:
        raise ValueError(f"Invalid ingest phase: {phase}")

    existing = session.scalar(
        select(IngestJob).where(
            IngestJob.document_id == document_id,
            IngestJob.status.in_(tuple(ACTIVE_JOB_STATUSES)),
        )
    )
    if existing is not None:
        return existing

    job = IngestJob(
        document_id=document_id,
        workspace_id=workspace_id,
        status="queued",
        phase=phase,
    )
    session.add(job)
    session.flush()
    return job


def claim_next_job(session: Session, phase_filter: str | None = None) -> IngestJob | None:
    """Claim the oldest queued job. Optionally filter by phase (SP-045b)."""
    stmt = (
        select(IngestJob)
        .where(IngestJob.status == "queued")
        .order_by(IngestJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if phase_filter is not None:
        stmt = stmt.where(IngestJob.phase == phase_filter)
    job = session.scalar(stmt)
    if job is None:
        return None
    job.status = "processing"
    session.flush()
    return job


def complete_job(session: Session, job: IngestJob) -> None:
    job.status = "completed"
    job.error = None
    session.flush()


def fail_job(session: Session, job: IngestJob, error: str) -> None:
    job.status = "failed"
    job.error = error
    session.flush()


def _pick_ingest_fn(phase: str):
    """Return the ingest function matching the job phase."""
    if phase == "fast":
        return ingest_document_fast
    return ingest_document  # heavy or full → full OCR + PYQ path


def process_claimed_job(session: Session, job: IngestJob) -> Document:
    job_id = job.id
    job = session.get(IngestJob, job_id)
    if job is None:
        raise ValueError(f"Ingest job {job_id} not found")

    document = session.get(Document, job.document_id)
    if document is None:
        fail_job(session, job, "Document not found")
        session.commit()
        raise ValueError("Document not found for ingest job")

    if not document.file_path:
        fail_job(session, job, "Document missing file_path")
        session.commit()
        raise ValueError("Document missing file_path")

    course = session.get(Course, document.course_id)
    quality = document.extraction_quality or {}
    upload_intent = quality.get("upload_intent")
    ingest_fn = _pick_ingest_fn(job.phase)

    try:
        result = ingest_fn(
            session,
            file_path=Path(document.file_path),
            course_id=document.course_id,
            doc_kind=document.doc_kind,
            course_name=course.name if course else document.course_id,
            upload_intent=upload_intent,
        )
        job = session.get(IngestJob, job_id)
        if job is None:
            raise ValueError(f"Ingest job {job_id} not found after ingest")
        if result.status == "failed":
            fail_job(session, job, result.error_message or "Ingest failed")
        else:
            complete_job(session, job)
        session.commit()
        session.refresh(job)
        return result
    except Exception as exc:
        session.rollback()
        job = session.get(IngestJob, job_id)
        if job is not None:
            fail_job(session, job, str(exc))
            session.commit()
        raise


_AUDIT_TIER_TO_PHASE: dict[str, str] = {
    "native": "fast",
    "ocr": "heavy",
    "layout_defer": "heavy",
}


def phase_for_audit_tier(audit_tier: str) -> str:
    """Map an SP-045a audit tier string to the ingest job phase (SP-045b)."""
    return _AUDIT_TIER_TO_PHASE.get(audit_tier, "full")


def enqueue_ingest_job_from_audit(
    session: Session,
    *,
    document_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    audit_tier: str | None = None,
) -> IngestJob:
    """Enqueue with phase derived from audit_tier (SP-045b). Falls back to 'full'."""
    phase = phase_for_audit_tier(audit_tier) if audit_tier else "full"
    return enqueue_ingest_job(session, document_id=document_id, workspace_id=workspace_id, phase=phase)


def drain_one_job(session: Session) -> IngestJob | None:
    job = claim_next_job(session)
    if job is None:
        session.commit()
        return None
    job_id = job.id
    session.commit()
    job = session.get(IngestJob, job_id)
    if job is None:
        return None
    process_claimed_job(session, job)
    return session.get(IngestJob, job_id)


def _progress_pct(job: IngestJob | None, document: Document) -> int | None:
    if document.status == "ready":
        return 100
    if document.status == "failed":
        return None
    if job is None:
        return 50 if document.status == "processing" else None
    if job.status == "queued":
        return 0
    if job.status == "processing":
        return 50
    if job.status == "completed":
        return 100 if document.status == "ready" else 75
    if job.status == "failed":
        return None
    return None


def get_latest_ingest_job(session: Session, document_id: uuid.UUID) -> IngestJob | None:
    return session.scalar(
        select(IngestJob)
        .where(IngestJob.document_id == document_id)
        .order_by(IngestJob.created_at.desc())
        .limit(1)
    )


def get_ingest_status(session: Session, document_id: uuid.UUID) -> dict | None:
    document = session.get(Document, document_id)
    if document is None:
        return None

    job = get_latest_ingest_job(session, document_id)
    status = job.status if job is not None else document.status
    phase = job.phase if job is not None else "full"
    error = (job.error if job is not None else None) or document.error_message

    return {
        "document_id": str(document.id),
        "job_id": str(job.id) if job is not None else None,
        "status": status,
        "phase": phase,
        "progress_pct": _progress_pct(job, document),
        "error": error,
        "document_status": document.status,
    }
