"""Idempotent document ingestion pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Chunk, ChunkEmbedding, ChunkParent, Course, Document, ExamQuestion
from app.services.workspaces import get_or_create_system_demo_workspace
from app.services.chunker.hierarchical import chunk_pages
from app.services.course_outline import outline_path_for_course
from app.services.embedder import embed_texts
from app.services.exam.pyq_parser import parse_exam_questions_from_pages
from app.services.pdf_extract import (
    annotate_pages_with_outline,
    audit_pdf,
    extract_pdf,
    load_outline,
    outline_summary,
    reconcile_audit_tier,
)

FIXTURE_QUALITY_HINTS: dict[str, dict] = {
    "PPL notes.pdf": {"source": "native_text", "header_strip": "MJCET"},
    "PPL previous papers.pdf": {"source": "mixed_scan"},
}

_REPO_ROOT = Path(__file__).resolve().parents[4]
OUTLINE_BY_FILENAME: dict[str, Path] = {
    "PPL notes.pdf": _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml",
}


def ensure_course(
    session: Session,
    course_id: str,
    name: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> Course:
    course = session.get(Course, course_id)
    if course:
        return course
    if workspace_id is None:
        workspace_id = get_or_create_system_demo_workspace(session).id
    course = Course(id=course_id, name=name or course_id, workspace_id=workspace_id)
    session.add(course)
    session.flush()
    return course


def _delete_document_chunks(session: Session, document_id: uuid.UUID) -> None:
    chunk_ids = select(Chunk.id).where(Chunk.document_id == document_id)
    session.execute(delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids)))
    session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    session.execute(delete(ChunkParent).where(ChunkParent.document_id == document_id))
    session.execute(delete(ExamQuestion).where(ExamQuestion.document_id == document_id))


def _persist_exam_questions(
    session: Session,
    *,
    document: Document,
    course_id: str,
    pages: list,
    quality: dict,
) -> None:
    outline = None
    outline_path = outline_path_for_course(course_id)
    if outline_path and outline_path.exists():
        outline = load_outline(outline_path)

    drafts = parse_exam_questions_from_pages(
        pages=pages,
        document_id=document.id,
        course_id=course_id,
        filename=document.filename,
        outline=outline,
    )
    for draft in drafts:
        session.add(
            ExamQuestion(
                document_id=document.id,
                course_id=course_id,
                page=draft.page,
                paper_label=draft.paper_label,
                part=draft.part,
                question_number=draft.question_number,
                prompt_text=draft.prompt_text,
                marks=draft.marks,
                unit=draft.unit,
                section_title=draft.section_title,
                extraction_method=draft.extraction_method,
                confidence=draft.confidence,
            )
        )
    quality["exam_questions_parsed"] = len(drafts)
    quality["exam_parse_method"] = "regex"
    if len(drafts) == 0:
        quality["exam_parse_warning"] = "regex parser found 0 exam questions"


def ingest_document_fast(
    session: Session,
    *,
    file_path: Path,
    course_id: str,
    doc_kind: str,
    course_name: str | None = None,
    upload_intent: str | None = None,
) -> Document:
    """Fast-phase ingest: native text only, no OCR, no PYQ parsing (SP-045b).

    Suitable for audit_tier=native documents. Produces study-ready chunks
    immediately; skips OCR fallback and past_paper exam question extraction.
    """
    from app.services.pdf_extract import ExtractionResult, PageText

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
        import fitz

        doc = fitz.open(file_path)
        pages: list[PageText] = []
        for i in range(len(doc)):
            text = doc[i].get_text("text", sort=True) or ""
            pages.append(PageText(page=i + 1, text=text.strip(), char_count=len(text.strip())))
        doc.close()

        total_chars = sum(p.char_count for p in pages)
        nonempty = sum(1 for p in pages if p.char_count > 0)
        quality_flags: dict = {
            "native_text_ratio": round(nonempty / max(len(pages), 1), 3),
            "ocr_page_count": 0,
            "avg_chars_per_page": round(total_chars / max(len(pages), 1), 1),
            "ingest_phase": "fast",
        }
        if nonempty == 0:
            quality_flags["partial"] = True

        extraction = ExtractionResult(
            pages=pages,
            page_count=len(pages),
            total_chars=total_chars,
            nonempty_pages=nonempty,
            ocr_pages=0,
            quality_flags=quality_flags,
        )

        quality = dict(quality_flags)
        hint = FIXTURE_QUALITY_HINTS.get(filename, {})
        for key, value in hint.items():
            if key not in quality:
                quality[key] = value
        quality["nonempty_pages"] = nonempty
        quality["total_pages"] = len(pages)
        if upload_intent is not None:
            quality["upload_intent"] = upload_intent

        outline_path = OUTLINE_BY_FILENAME.get(filename)
        if outline_path and outline_path.exists():
            outline = load_outline(outline_path)
            annotate_pages_with_outline(extraction.pages, outline)
            quality["outline"] = outline_summary(outline, outline_path.name)
        elif doc_kind == "notes" and upload_intent != "quick":
            from app.services.course_outline import maybe_extract_outline_on_notes_ingest

            extracted = maybe_extract_outline_on_notes_ingest(
                session,
                course_id=course_id,
                filename=filename,
                file_path=file_path,
                pages=extraction.pages,
            )
            if extracted:
                quality["outline"] = extracted

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

        document.page_count = len(pages)
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


def ingest_document(
    session: Session,
    *,
    file_path: Path,
    course_id: str,
    doc_kind: str,
    course_name: str | None = None,
    upload_intent: str | None = None,
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
        audit = audit_pdf(file_path)
        extraction = extract_pdf(file_path)
        quality = dict(extraction.quality_flags)
        quality.update(audit.as_quality_fields())
        quality["audit_tier"] = reconcile_audit_tier(audit, extraction)
        hint = FIXTURE_QUALITY_HINTS.get(filename, {})
        # Static metadata only — do not override extract_pdf partial/needs_ocr flags.
        for key, value in hint.items():
            if key not in quality:
                quality[key] = value
        quality["nonempty_pages"] = extraction.nonempty_pages
        quality["total_pages"] = extraction.page_count
        if upload_intent is not None:
            quality["upload_intent"] = upload_intent

        outline_path = OUTLINE_BY_FILENAME.get(filename)
        if outline_path and outline_path.exists():
            outline = load_outline(outline_path)
            annotate_pages_with_outline(extraction.pages, outline)
            quality["outline"] = outline_summary(outline, outline_path.name)
        elif doc_kind == "notes" and upload_intent != "quick":
            from app.services.course_outline import maybe_extract_outline_on_notes_ingest

            extracted = maybe_extract_outline_on_notes_ingest(
                session,
                course_id=course_id,
                filename=filename,
                file_path=file_path,
                pages=extraction.pages,
            )
            if extracted:
                quality["outline"] = extracted

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

        if doc_kind == "past_paper":
            _persist_exam_questions(
                session,
                document=document,
                course_id=course_id,
                pages=extraction.pages,
                quality=quality,
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
