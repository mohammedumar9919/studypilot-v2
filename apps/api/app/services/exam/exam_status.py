"""Unified exam index / heatmap readiness for a course (read-only, no LLM)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chunk, ChunkEmbedding, Course, Document, ExamQuestion
from app.services.exam.topic_frequency import (
    _READABLE_CHAR_THRESHOLD,
    _fetch_past_paper_chunks,
    _fetch_past_paper_documents,
    _seed_path,
    _source_documents,
    count_parsed_questions,
)


def compute_exam_status(session: Session, course_id: str) -> dict[str, Any]:
    """Return exam corpus + index readiness for Agent E empty states and gating."""
    course = session.get(Course, course_id)
    if course is None:
        return {"found": False, "course_id": course_id}

    documents = _fetch_past_paper_documents(session, course_id)
    chunks = _fetch_past_paper_chunks(session, course_id)
    source_documents = _source_documents(chunks)

    document_count = len(documents)
    documents_ready = document_count > 0
    total_pages = sum(doc.page_count or 0 for doc in documents)
    readable_pages = sum(len(entry.get("readable_pages") or []) for entry in source_documents)
    chunk_count = len(chunks)

    embedded_chunk_count = 0
    if chunk_count > 0:
        embedded_chunk_count = session.scalar(
            select(func.count(Chunk.id))
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Document.course_id == course_id,
                Document.doc_kind == "past_paper",
                Document.status == "ready",
            )
        ) or 0

    embeddings_ready = chunk_count > 0 and embedded_chunk_count >= chunk_count
    has_pyq_seed = _seed_path(course_id) is not None
    parsed_questions = count_parsed_questions(session, course_id)
    question_count_source = "exam_questions" if parsed_questions > 0 else "none"
    exam_index_ready = documents_ready and chunk_count > 0 and embeddings_ready
    heatmap_available = documents_ready and (
        parsed_questions > 0 or has_pyq_seed or readable_pages > 0
    )

    if parsed_questions > 0:
        heatmap_source = "parsed"
    elif has_pyq_seed:
        heatmap_source = "seed"
    elif readable_pages > 0:
        heatmap_source = "keyword"
    else:
        heatmap_source = "none"

    return {
        "found": True,
        "course_id": course_id,
        "documents_ready": documents_ready,
        "document_count": document_count,
        "readable_pages": readable_pages,
        "total_pages": total_pages,
        "chunk_count": chunk_count,
        "embedded_chunk_count": embedded_chunk_count,
        "embeddings_ready": embeddings_ready,
        "parsed_questions": parsed_questions,
        "question_count_source": question_count_source,
        "has_pyq_seed": has_pyq_seed,
        "exam_index_ready": exam_index_ready,
        "heatmap_available": heatmap_available,
        "heatmap_source": heatmap_source,
        "readable_char_threshold": _READABLE_CHAR_THRESHOLD,
        "source_documents": source_documents,
    }
