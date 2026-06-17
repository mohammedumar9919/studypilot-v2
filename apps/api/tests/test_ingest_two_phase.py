"""Tests for SP-045b two-phase ingest routing."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models import Document, IngestJob
from app.services.ingest_queue import (
    claim_next_job,
    enqueue_ingest_job,
    enqueue_ingest_job_from_audit,
    phase_for_audit_tier,
    process_claimed_job,
)
from app.services.ingestion import ingest_document_fast
from tests.conftest import add_test_course

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"


# --- phase_for_audit_tier ---

def test_phase_for_native_is_fast() -> None:
    assert phase_for_audit_tier("native") == "fast"


def test_phase_for_ocr_is_heavy() -> None:
    assert phase_for_audit_tier("ocr") == "heavy"


def test_phase_for_layout_defer_is_heavy() -> None:
    assert phase_for_audit_tier("layout_defer") == "heavy"


def test_phase_for_unknown_is_full() -> None:
    assert phase_for_audit_tier("unknown_tier") == "full"


# --- enqueue_ingest_job_from_audit ---

def test_enqueue_from_audit_native_gives_fast_phase(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        course_id="PPL",
        filename="fast-audit.pdf",
        doc_kind="notes",
        status="pending",
        file_path="/tmp/fast-audit.pdf",
    )
    db_session.add(doc)
    db_session.flush()

    job = enqueue_ingest_job_from_audit(db_session, document_id=doc.id, audit_tier="native")
    db_session.commit()

    assert job.phase == "fast"
    assert job.status == "queued"


def test_enqueue_from_audit_ocr_gives_heavy_phase(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        course_id="PPL",
        filename="heavy-audit.pdf",
        doc_kind="past_paper",
        status="pending",
        file_path="/tmp/heavy-audit.pdf",
    )
    db_session.add(doc)
    db_session.flush()

    job = enqueue_ingest_job_from_audit(db_session, document_id=doc.id, audit_tier="ocr")
    db_session.commit()

    assert job.phase == "heavy"


def test_enqueue_from_audit_none_gives_full_phase(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        course_id="PPL",
        filename="full-audit.pdf",
        doc_kind="notes",
        status="pending",
        file_path="/tmp/full-audit.pdf",
    )
    db_session.add(doc)
    db_session.flush()

    job = enqueue_ingest_job_from_audit(db_session, document_id=doc.id, audit_tier=None)
    db_session.commit()

    assert job.phase == "full"


# --- claim_next_job phase_filter ---

def test_claim_next_job_phase_filter(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")

    def make_doc(name: str) -> Document:
        doc = Document(
            course_id="PPL",
            filename=name,
            doc_kind="notes",
            status="pending",
            file_path=f"/tmp/{name}",
        )
        db_session.add(doc)
        db_session.flush()
        return doc

    d_fast = make_doc("fast-filter.pdf")
    d_heavy = make_doc("heavy-filter.pdf")

    enqueue_ingest_job(db_session, document_id=d_fast.id, phase="fast")
    enqueue_ingest_job(db_session, document_id=d_heavy.id, phase="heavy")
    db_session.commit()

    heavy_job = claim_next_job(db_session, phase_filter="heavy")
    assert heavy_job is not None
    assert heavy_job.phase == "heavy"
    assert heavy_job.status == "processing"

    fast_job = claim_next_job(db_session, phase_filter="fast")
    assert fast_job is not None
    assert fast_job.phase == "fast"
    db_session.commit()


# --- process_claimed_job routes to fast fn ---

@pytest.mark.skipif(not NOTES_PDF.exists(), reason="Missing PPL notes fixture")
def test_process_fast_job_uses_fast_ingest(db_session, tmp_path) -> None:
    add_test_course(db_session, "PPL", "PPL")
    dest = tmp_path / "ppl_notes_copy.pdf"
    shutil.copy(NOTES_PDF, dest)

    doc = Document(
        course_id="PPL",
        filename=dest.name,
        doc_kind="notes",
        status="pending",
        file_path=str(dest),
    )
    db_session.add(doc)
    db_session.flush()
    job = enqueue_ingest_job(db_session, document_id=doc.id, phase="fast")
    db_session.commit()

    with patch("app.services.ingest_queue.ingest_document") as mock_full, \
         patch("app.services.ingest_queue.ingest_document_fast") as mock_fast:

        ready_doc = Document(
            course_id="PPL",
            filename=dest.name,
            doc_kind="notes",
            status="ready",
            page_count=94,
            file_path=str(dest),
        )
        mock_fast.return_value = ready_doc

        job = db_session.get(IngestJob, job.id)
        process_claimed_job(db_session, job)

        mock_fast.assert_called_once()
        mock_full.assert_not_called()


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="Missing PPL notes fixture")
def test_process_heavy_job_uses_full_ingest(db_session, tmp_path) -> None:
    add_test_course(db_session, "PPL", "PPL")
    dest = tmp_path / "ppl_notes_heavy.pdf"
    shutil.copy(NOTES_PDF, dest)

    doc = Document(
        course_id="PPL",
        filename=dest.name,
        doc_kind="notes",
        status="pending",
        file_path=str(dest),
    )
    db_session.add(doc)
    db_session.flush()
    job = enqueue_ingest_job(db_session, document_id=doc.id, phase="heavy")
    db_session.commit()

    with patch("app.services.ingest_queue.ingest_document") as mock_full, \
         patch("app.services.ingest_queue.ingest_document_fast") as mock_fast:

        ready_doc = Document(
            course_id="PPL",
            filename=dest.name,
            doc_kind="notes",
            status="ready",
            page_count=94,
            file_path=str(dest),
        )
        mock_full.return_value = ready_doc

        job = db_session.get(IngestJob, job.id)
        process_claimed_job(db_session, job)

        mock_full.assert_called_once()
        mock_fast.assert_not_called()


# --- ingest_document_fast integration ---

@pytest.mark.skipif(not NOTES_PDF.exists(), reason="Missing PPL notes fixture")
def test_ingest_document_fast_ppl_notes_ready(db_session) -> None:
    doc = ingest_document_fast(
        db_session,
        file_path=NOTES_PDF,
        course_id="PPL",
        doc_kind="notes",
    )
    assert doc.status == "ready"
    assert doc.page_count == 94
    quality = doc.extraction_quality or {}
    assert quality.get("ingest_phase") == "fast"
    assert quality.get("ocr_page_count") == 0
    assert quality.get("nonempty_pages", 0) > 50
