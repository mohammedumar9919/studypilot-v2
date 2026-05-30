"""Idempotent document ingestion pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Chunk, ChunkEmbedding, ChunkParent, Course, Document
from app.services.chunker.hierarchical import chunk_pages
from app.services.embedder import embed_texts
from app.services.pdf_extract import (
    annotate_pages_with_outline,
    extract_pdf,
    load_outline,
    outline_summary,
)

FIXTURE_QUALITY_HINTS: dict[str, dict] = {
    "PPL notes.pdf": {"source": "native_text", "header_strip": "MJCET"},
    "PPL previous papers.pdf": {"source": "mixed_scan"},
}

_REPO_ROOT = Path(__file__).resolve().parents[4]
OUTLINE_BY_FILENAME: dict[str, Path] = {
    "PPL notes.pdf": _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml",
}


def ensure_course(session: Session, course_id: str, name: str | None = None) -> Course:
    course = session.get(Course, course_id)
    if course:
        return course
    course = Course(id=course_id, name=name or course_id)
    session.add(course)
    session.flush()
    return course


def _delete_document_chunks(session: Session, document_id: uuid.UUID) -> None:
    chunk_ids = select(Chunk.id).where(Chunk.document_id == document_id)
    session.execute(delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids)))
    session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    session.execute(delete(ChunkParent).where(ChunkParent.document_id == document_id))


def ingest_document(
    session: Session,
    *,
    file_path: Path,
    course_id: str,
    doc_kind: str,
    course_name: str | None = None,
) -> Document:
    file_path = file_path.resolve()
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    ensure_course(session, course_id, course_name)
    filename = file_path.name

    existing = session.scalar(
        select(Document).where(
            Document.course_id == course_id,
            Document.filename == filename,
            Document.doc_kind == doc_kind,
        )
    )

    if existing:
        document = existing
        _delete_document_chunks(session, document.id)
        document.status = "processing"
        document.error_message = None
    else:
        document = Document(
            course_id=course_id,
            filename=filename,
            doc_kind=doc_kind,
            status="processing",
            file_path=str(file_path),
        )
        session.add(document)
    session.flush()
    document_id = document.id

    try:
        extraction = extract_pdf(file_path)
        quality = dict(extraction.quality_flags)
        hint = FIXTURE_QUALITY_HINTS.get(filename, {})
        # Static metadata only — do not override extract_pdf partial/needs_ocr flags.
        for key, value in hint.items():
            if key not in quality:
                quality[key] = value
        quality["nonempty_pages"] = extraction.nonempty_pages
        quality["total_pages"] = extraction.page_count

        outline_path = OUTLINE_BY_FILENAME.get(filename)
        if outline_path and outline_path.exists():
            outline = load_outline(outline_path)
            annotate_pages_with_outline(extraction.pages, outline)
            quality["outline"] = outline_summary(outline, outline_path.name)

        chunked = chunk_pages(extraction.pages, doc_kind)
        if not chunked.children:
            document.status = "failed"
            document.error_message = "No text extracted from PDF"
            document.extraction_quality = quality
            session.commit()
            session.refresh(document)
            return document

        parent_ids: list[uuid.UUID] = []
        for parent in chunked.parents:
            row = ChunkParent(
                document_id=document_id,
                page_start=parent.page_start,
                page_end=parent.page_end,
                text=parent.text,
                metadata_=parent.metadata,
            )
            session.add(row)
            session.flush()
            parent_ids.append(row.id)

        chunk_rows: list[Chunk] = []
        for child in chunked.children:
            row = Chunk(
                parent_id=parent_ids[child.parent_index],
                document_id=document_id,
                chunk_index=child.chunk_index,
                page=child.page,
                text=child.text,
                token_count=child.token_count,
                metadata_=child.metadata,
            )
            session.add(row)
            chunk_rows.append(row)
        session.flush()

        vectors = embed_texts([c.text for c in chunk_rows])
        for chunk, vector in zip(chunk_rows, vectors, strict=True):
            session.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    embedding=vector,
                    embedding_model="BAAI/bge-small-en-v1.5",
                    dimensions=len(vector),
                )
            )

        document.page_count = extraction.page_count
        document.file_path = str(file_path)
        document.extraction_quality = quality
        document.status = "ready"
        document.error_message = None
        session.commit()
        session.refresh(document)
        return document

    except Exception as exc:
        session.rollback()
        document = session.get(Document, document_id)
        if document:
            document.status = "failed"
            document.error_message = str(exc)
            session.commit()
            session.refresh(document)
        raise
