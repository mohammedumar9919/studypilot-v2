"""Multipart PDF upload → ingest_document (sync v1)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Document
from app.services.ingestion import ingest_document

API_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = API_ROOT / ".uploads"

ALLOWED_DOC_KINDS = frozenset({"notes", "textbook", "syllabus", "past_paper"})


class UploadValidationError(ValueError):
    """Invalid upload request (bad kind, non-PDF)."""


class IngestFailedError(Exception):
    """Ingest pipeline returned failed status or raised."""

    def __init__(self, message: str, *, document: Document | None = None) -> None:
        super().__init__(message)
        self.document = document


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


def serialize_document(document: Document) -> dict:
    return {
        "document_id": str(document.id),
        "course_id": document.course_id,
        "filename": document.filename,
        "doc_kind": document.doc_kind,
        "status": document.status,
        "page_count": document.page_count,
        "extraction_quality": document.extraction_quality,
    }


def upload_and_ingest_document(
    session: Session,
    *,
    course_id: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    doc_kind: str,
) -> dict:
    """Validate upload, save to disk, run sync ingest, return API metadata."""
    validate_upload(filename=filename, content_type=content_type, doc_kind=doc_kind)
    file_path = save_upload_to_disk(course_id, filename, data)

    try:
        document = ingest_document(
            session,
            file_path=file_path,
            course_id=course_id,
            doc_kind=doc_kind,
            course_name=course_id,
        )
    except Exception as exc:
        raise IngestFailedError(str(exc)) from exc

    if document.status == "failed":
        raise IngestFailedError(
            document.error_message or "Ingest failed",
            document=document,
        )

    return serialize_document(document)
