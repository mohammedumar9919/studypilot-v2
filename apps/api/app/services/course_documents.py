"""Course document listing and source_ids validation for scoped retrieval."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Document
from app.services.rag.retrieve import EXAM_DOC_KINDS, STUDY_DOC_KINDS

VISIBLE_STATUSES = ("ready", "processing")


def list_course_documents(session: Session, course_id: str) -> list[Document]:
    """Ready/processing documents for a course, ordered by created_at then filename."""
    stmt = (
        select(Document)
        .where(
            Document.course_id == course_id,
            Document.status.in_(VISIBLE_STATUSES),
        )
        .order_by(Document.created_at, Document.filename)
    )
    return list(session.scalars(stmt).all())


def serialize_document(document: Document) -> dict[str, Any]:
    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "page_count": document.page_count,
        "status": document.status,
        "doc_kind": document.doc_kind,
    }


def get_course_documents(session: Session, course_id: str) -> dict[str, Any] | None:
    """Return documents JSON for a course, or None if the course is unknown."""
    course = session.get(Course, course_id)
    if course is None:
        return None

    documents = list_course_documents(session, course_id)
    return {
        "course_id": course_id,
        "documents": [serialize_document(document) for document in documents],
    }


def validate_source_ids(
    session: Session,
    *,
    course_id: str,
    source_ids: list[str],
    preset: str,
) -> list[uuid.UUID]:
    """Parse and validate source_ids for scoped retrieval. Raises ValueError (400)."""
    if not source_ids:
        raise ValueError("source_ids must not be empty when provided")

    allowed_kinds = set(EXAM_DOC_KINDS if preset == "exam" else STUDY_DOC_KINDS)
    parsed: list[uuid.UUID] = []

    for raw_id in source_ids:
        try:
            doc_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise ValueError(f"Invalid source_ids UUID: {raw_id}") from exc

        document = session.get(Document, doc_id)
        if document is None or document.course_id != course_id:
            raise ValueError(f"Document not found for course: {raw_id}")
        if document.status not in VISIBLE_STATUSES:
            raise ValueError(f"Document status not usable for retrieval: {raw_id}")
        if document.doc_kind not in allowed_kinds:
            raise ValueError(
                f"Document doc_kind not allowed for preset {preset}: {raw_id}"
            )

        parsed.append(doc_id)

    return parsed
