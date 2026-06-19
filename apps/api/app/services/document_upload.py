"""Multipart PDF upload → ingest_document (sync v1) or enqueue (async SP-013a)."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Document
from app.services.ingest_queue import enqueue_ingest_job_from_audit, is_ingest_async_enabled
from app.services.ingestion import ensure_course, ingest_document

API_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = API_ROOT / ".uploads"

ALLOWED_DOC_KINDS = frozenset({"notes", "textbook", "syllabus", "past_paper"})
ALLOWED_UPLOAD_INTENTS = frozenset({"quick", "topic", "past_paper", "syllabus"})
DEFAULT_UPLOAD_INTENT = "quick"


class UploadValidationError(ValueError):
    """Invalid upload request (bad kind, non-PDF)."""


class IngestFailedError(Exception):
    """Ingest pipeline returned failed status or raised."""

    def __init__(self, message: str, *, document: Document | None = None) -> None:
        super().__init__(message)
        self.document = document


def normalize_upload_intent(upload_intent: str | None) -> str:
    if upload_intent is None or upload_intent.strip() == "":
        return DEFAULT_UPLOAD_INTENT
    return upload_intent.strip()


def validate_upload_intent(*, doc_kind: str, upload_intent: str) -> None:
    if upload_intent not in ALLOWED_UPLOAD_INTENTS:
        raise UploadValidationError(
            f"Invalid upload_intent: {upload_intent}. "
            f"Must be one of: {', '.join(sorted(ALLOWED_UPLOAD_INTENTS))}"
        )
    if doc_kind == "past_paper" and upload_intent != "past_paper":
        raise UploadValidationError("doc_kind past_paper requires upload_intent past_paper")
    if doc_kind == "syllabus" and upload_intent != "syllabus":
        raise UploadValidationError("doc_kind syllabus requires upload_intent syllabus")
    if doc_kind in ("notes", "textbook") and upload_intent not in ("quick", "topic", "syllabus"):
        raise UploadValidationError(
            f"doc_kind {doc_kind} requires upload_intent in quick, topic, syllabus"
        )


def validate_upload(*, filename: str, content_type: str | None, doc_kind: str) -> None:
    if doc_kind not in ALLOWED_DOC_KINDS:
        raise UploadValidationError(
            f"Invalid doc_kind: {doc_kind}. Must be one of: {', '.join(sorted(ALLOWED_DOC_KINDS))}"
        )
    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError("Only PDF uploads are supported")
    if content_type and content_type not in (
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    ):
        raise UploadValidationError(f"Unsupported content type: {content_type}")


def save_upload_to_disk(course_id: str, filename: str, data: bytes) -> Path:
    """Persist uploaded PDF for idempotent re-ingest (same path as CLI file)."""
    safe_name = Path(filename).name
    dest_dir = UPLOAD_ROOT / course_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(data)
    return dest_path


def serialize_document(document: Document, *, job_id: uuid.UUID | None = None) -> dict:
    quality = document.extraction_quality or {}
    status = document.status
    if job_id is not None and is_ingest_async_enabled() and status == "pending":
        status = "queued"
    payload = {
        "document_id": str(document.id),
        "course_id": document.course_id,
        "filename": document.filename,
        "doc_kind": document.doc_kind,
        "status": status,
        "page_count": document.page_count,
        "upload_intent": quality.get("upload_intent"),
        "extraction_quality": document.extraction_quality,
    }
    if job_id is not None:
        payload["job_id"] = str(job_id)
    return payload


def _create_or_reset_pending_document(
    session: Session,
    *,
    course_id: str,
    filename: str,
    doc_kind: str,
    file_path: Path,
    upload_intent: str,
) -> Document:
    ensure_course(session, course_id, course_id)
    safe_name = Path(filename).name
    existing = session.scalar(
        select(Document).where(
            Document.course_id == course_id,
            Document.filename == safe_name,
            Document.doc_kind == doc_kind,
        )
    )
    quality = {"upload_intent": upload_intent}
    if existing is not None:
        existing.status = "pending"
        existing.file_path = str(file_path)
        existing.extraction_quality = quality
        existing.error_message = None
        existing.page_count = None
        document = existing
    else:
        document = Document(
            course_id=course_id,
            filename=safe_name,
            doc_kind=doc_kind,
            status="pending",
            file_path=str(file_path),
            extraction_quality=quality,
        )
        session.add(document)
    session.flush()
    return document


def upload_and_ingest_document(
    session: Session,
    *,
    course_id: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    doc_kind: str,
    upload_intent: str | None = None,
) -> dict:
    """Validate upload, save to disk, sync ingest or enqueue when async enabled."""
    resolved_intent = normalize_upload_intent(upload_intent)
    validate_upload(filename=filename, content_type=content_type, doc_kind=doc_kind)
    validate_upload_intent(doc_kind=doc_kind, upload_intent=resolved_intent)
    file_path = save_upload_to_disk(course_id, filename, data)

    if is_ingest_async_enabled():
        document = _create_or_reset_pending_document(
            session,
            course_id=course_id,
            filename=filename,
            doc_kind=doc_kind,
            file_path=file_path,
            upload_intent=resolved_intent,
        )
        course = session.get(Course, course_id)
        workspace_id = course.workspace_id if course else None
        # SP-045b: quick audit to pick fast vs heavy phase without full extract
        from app.services.pdf_extract import audit_pdf

        try:
            audit = audit_pdf(file_path)
            audit_tier: str | None = audit.tier
        except Exception:
            audit_tier = None
        job = enqueue_ingest_job_from_audit(
            session,
            document_id=document.id,
            workspace_id=workspace_id,
            audit_tier=audit_tier,
        )
        session.commit()
        session.refresh(document)
        return serialize_document(document, job_id=job.id)

    try:
        document = ingest_document(
            session,
            file_path=file_path,
            course_id=course_id,
            doc_kind=doc_kind,
            course_name=course_id,
            upload_intent=resolved_intent,
        )
    except Exception as exc:
        raise IngestFailedError(str(exc)) from exc

    if document.status == "failed":
        raise IngestFailedError(
            document.error_message or "Ingest failed",
            document=document,
        )

    return serialize_document(document)
