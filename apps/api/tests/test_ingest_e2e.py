import os
from pathlib import Path

import pytest

from app.models import Chunk, Document
from app.services.ingestion import ingest_document

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"


@pytest.fixture(autouse=True)
def _require_fixtures():
    if not NOTES_PDF.exists():
        pytest.skip(f"Missing fixture: {NOTES_PDF}")


def test_ingest_ppl_notes(db_session) -> None:
    doc = ingest_document(
        db_session,
        file_path=NOTES_PDF,
        course_id="PPL",
        doc_kind="notes",
    )
    assert doc.status == "ready"
    assert doc.page_count == 94
    assert doc.extraction_quality is not None
    assert doc.extraction_quality.get("nonempty_pages", 0) > 50

    outline = doc.extraction_quality.get("outline") or {}
    assert outline.get("unit_count") == 5
    assert outline.get("needs_human_review") is True

    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).all()
    assert len(chunks) > 20
    chunks_with_unit = [c for c in chunks if (c.metadata_ or {}).get("unit")]
    assert len(chunks_with_unit) > 20
    assert any((c.metadata_ or {}).get("toc_path", "").startswith("Unit 1 >") for c in chunks)


def test_ingest_ppl_papers_flags_partial(db_session) -> None:
    if not PAPERS_PDF.exists():
        pytest.skip("Missing past papers fixture")
    doc = ingest_document(
        db_session,
        file_path=PAPERS_PDF,
        course_id="PPL",
        doc_kind="past_paper",
    )
    assert doc.status == "ready"
    quality = doc.extraction_quality or {}
    assert quality.get("partial") is True or quality.get("needs_ocr") is True
    assert quality.get("exam_parse_method") == "regex"


def test_ingest_idempotent(db_session) -> None:
    doc1 = ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    count1 = db_session.query(Chunk).filter(Chunk.document_id == doc1.id).count()
    doc2 = ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    count2 = db_session.query(Chunk).filter(Chunk.document_id == doc2.id).count()
    assert doc1.id == doc2.id
    assert count1 == count2
