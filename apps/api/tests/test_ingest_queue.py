"""Tests for Postgres ingest job queue (SP-013a)."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models import Document, IngestJob
from app.services.document_upload import upload_and_ingest_document
from app.services.ingest_queue import (
    claim_next_job,
    drain_one_job,
    enqueue_ingest_job,
    is_ingest_async_enabled,
    process_claimed_job,
)
from tests.conftest import add_test_course

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"


@pytest.fixture()
def notes_pdf_copy(tmp_path: Path) -> Path:
    """Unique on-disk copy so worker tests do not collide with upload e2e."""
    dest = tmp_path / f"queue-worker-{uuid.uuid4().hex}.pdf"
    shutil.copy(NOTES_PDF, dest)
    return dest


@pytest.fixture(autouse=True)
def _require_notes_fixture():
    if not NOTES_PDF.exists():
        pytest.skip(f"Missing fixture: {NOTES_PDF}")


def test_is_ingest_async_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("STUDYPILOT_INGEST_ASYNC", raising=False)
    assert is_ingest_async_enabled() is False


def test_is_ingest_async_enabled_when_flag_set(monkeypatch) -> None:
    monkeypatch.setenv("STUDYPILOT_INGEST_ASYNC", "1")
    assert is_ingest_async_enabled() is True


def test_enqueue_creates_queued_job(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename="queue-test.pdf",
        doc_kind="notes",
        status="pending",
        file_path=str(NOTES_PDF),
    )
    db_session.add(document)
    db_session.flush()

    job = enqueue_ingest_job(db_session, document_id=document.id, phase="full")
    db_session.commit()

    assert job.id is not None
    assert job.document_id == document.id
    assert job.status == "queued"
    assert job.phase == "full"
    assert job.error is None


def test_enqueue_idempotent_for_active_job(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename="dup-queue.pdf",
        doc_kind="notes",
        status="pending",
    )
    db_session.add(document)
    db_session.flush()

    first = enqueue_ingest_job(db_session, document_id=document.id)
    second = enqueue_ingest_job(db_session, document_id=document.id)
    db_session.commit()

    assert first.id == second.id
    jobs = db_session.query(IngestJob).filter(IngestJob.document_id == document.id).all()
    assert len(jobs) == 1


def test_worker_drains_job_to_ready(db_session, notes_pdf_copy: Path) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename=notes_pdf_copy.name,
        doc_kind="notes",
        status="pending",
        file_path=str(notes_pdf_copy),
        extraction_quality={"upload_intent": "quick"},
    )
    db_session.add(document)
    db_session.flush()
    job = enqueue_ingest_job(db_session, document_id=document.id, phase="full")
    db_session.commit()
    job_id = job.id

    claimed = claim_next_job(db_session)
    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.status == "processing"
    db_session.commit()

    result = process_claimed_job(db_session, claimed)
    assert result.status == "ready"
    assert result.page_count == 94

    finished = db_session.get(IngestJob, job_id)
    assert finished is not None
    assert finished.status == "completed"
    assert finished.error is None


def test_drain_one_job_helper(db_session, notes_pdf_copy: Path) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename=notes_pdf_copy.name,
        doc_kind="notes",
        status="pending",
        file_path=str(notes_pdf_copy),
        extraction_quality={"upload_intent": "quick"},
    )
    db_session.add(document)
    db_session.flush()
    enqueue_ingest_job(db_session, document_id=document.id)
    db_session.commit()

    finished = drain_one_job(db_session)
    assert finished is not None
    assert finished.status == "completed"

    document = db_session.get(Document, document.id)
    assert document is not None
    assert document.status == "ready"


@patch.dict(os.environ, {"STUDYPILOT_INGEST_ASYNC": "1"}, clear=False)
def test_async_upload_enqueues_without_sync_ingest(db_session, tmp_path, monkeypatch) -> None:
    add_test_course(db_session, "PPL", "PPL")
    pdf_bytes = NOTES_PDF.read_bytes()

    with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
        with patch("app.services.document_upload.ingest_document") as mock_ingest:
            result = upload_and_ingest_document(
                db_session,
                course_id="PPL",
                filename="PPL notes.pdf",
                content_type="application/pdf",
                data=pdf_bytes,
                doc_kind="notes",
            )

    mock_ingest.assert_not_called()
    assert result["status"] == "queued"
    assert result["job_id"]
    assert result["upload_intent"] == "quick"

    document = db_session.get(Document, uuid.UUID(result["document_id"]))
    assert document is not None
    assert document.status == "pending"

    job = db_session.get(IngestJob, uuid.UUID(result["job_id"]))
    assert job is not None
    assert job.status == "queued"
