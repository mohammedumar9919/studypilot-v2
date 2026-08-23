"""Course document listing and source_ids validation for scoped retrieval."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    Chunk,
    ChunkEmbedding,
    ChunkParent,
    Course,
    Document,
    ExamQuestion,
    ExamQuestionConcept,
    IngestJob,
)
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


def parse_document_id_list(raw_ids: list[str] | None) -> list[uuid.UUID] | None:
    if not raw_ids:
        return None
    parsed: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            parsed.append(uuid.UUID(raw_id))
        except ValueError as exc:
            raise ValueError(f"Invalid document_ids UUID: {raw_id}") from exc
    return parsed


def _delete_document_artifacts(session: Session, document_id: uuid.UUID) -> None:
    question_ids = select(ExamQuestion.id).where(ExamQuestion.document_id == document_id)
    session.execute(
        delete(ExamQuestionConcept).where(ExamQuestionConcept.question_id.in_(question_ids))
    )
    chunk_ids = select(Chunk.id).where(Chunk.document_id == document_id)
    session.execute(delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids)))
    session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    session.execute(delete(ChunkParent).where(ChunkParent.document_id == document_id))
    session.execute(delete(ExamQuestion).where(ExamQuestion.document_id == document_id))
    session.execute(delete(IngestJob).where(IngestJob.document_id == document_id))


def delete_course_document(
    session: Session,
    course_id: str,
    document_id: uuid.UUID,
) -> dict[str, Any]:
    """Delete an ingested document and its chunks / exam questions for a course."""
    document = session.get(Document, document_id)
    if document is None or document.course_id != course_id:
        return {"found": False, "course_id": course_id, "document_id": str(document_id)}

    was_past_paper = document.doc_kind == "past_paper"
    filename = document.filename
    doc_kind = document.doc_kind
    _delete_document_artifacts(session, document_id)
    session.delete(document)
    session.flush()

    concepts_rebuild = "deferred"
    if was_past_paper:
        from app.services.exam.concept_derive import derive_exam_concepts_for_course

        derive_exam_concepts_for_course(session, course_id)
        concepts_rebuild = "completed"

    return {
        "found": True,
        "course_id": course_id,
        "document_id": str(document_id),
        "filename": filename,
        "doc_kind": doc_kind,
        "was_past_paper": was_past_paper,
        "concepts_rebuild": concepts_rebuild,
    }


def list_past_paper_documents(session: Session, course_id: str) -> list[dict[str, Any]]:
    documents = list_course_documents(session, course_id)
    past_papers = [document for document in documents if document.doc_kind == "past_paper"]
    if not past_papers:
        return []

    counts = dict(
        session.execute(
            select(ExamQuestion.document_id, func.count())
            .where(
                ExamQuestion.course_id == course_id,
                ExamQuestion.document_id.in_([document.id for document in past_papers]),
            )
            .group_by(ExamQuestion.document_id)
        ).all()
    )
    return [
        {
            **serialize_document(document),
            "parsed_question_count": int(counts.get(document.id, 0)),
        }
        for document in past_papers
    ]


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
