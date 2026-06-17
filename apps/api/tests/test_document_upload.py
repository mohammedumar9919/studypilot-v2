"""Tests for POST /api/v1/courses/{course_id}/documents (multipart upload)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Document
from app.services.document_upload import (
    UploadValidationError,
    upload_and_ingest_document,
    validate_upload,
)
from tests.conftest import add_test_course

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"

client = TestClient(app)


@pytest.fixture(autouse=True)
def _bind_fastapi_db(db_session):
    """All upload API tests share the locked test session (avoids parallel DB deadlocks)."""

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


def test_validate_upload_rejects_invalid_doc_kind() -> None:
    with pytest.raises(UploadValidationError, match="Invalid doc_kind"):
        validate_upload(filename="notes.pdf", content_type="application/pdf", doc_kind="invalid")


def test_validate_upload_rejects_non_pdf() -> None:
    with pytest.raises(UploadValidationError, match="PDF"):
        validate_upload(filename="notes.txt", content_type="text/plain", doc_kind="notes")


@patch("app.services.document_upload.is_ingest_async_enabled", return_value=False)
@patch("app.services.document_upload.ingest_document")
def test_upload_and_ingest_returns_metadata(mock_ingest, _mock_async, db_session, tmp_path) -> None:
    doc_id = uuid.uuid4()
    mock_ingest.return_value = Document(
        id=doc_id,
        course_id="PPL",
        filename="sample.pdf",
        doc_kind="notes",
        status="ready",
        page_count=10,
        extraction_quality={"nonempty_pages": 10, "upload_intent": "quick"},
    )

    with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
        result = upload_and_ingest_document(
            db_session,
            course_id="PPL",
            filename="sample.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.4 fake",
            doc_kind="notes",
        )

    assert result["document_id"] == str(doc_id)
    assert result["course_id"] == "PPL"
    assert result["filename"] == "sample.pdf"
    assert result["doc_kind"] == "notes"
    assert result["status"] == "ready"
    assert result["page_count"] == 10
    assert result["upload_intent"] == "quick"
    assert result["extraction_quality"]["nonempty_pages"] == 10
    mock_ingest.assert_called_once()
    _, kwargs = mock_ingest.call_args
    assert kwargs["upload_intent"] == "quick"


@patch("app.services.document_upload.is_ingest_async_enabled", return_value=False)
@patch("app.services.document_upload.ingest_document")
def test_upload_and_ingest_raises_on_failed_status(mock_ingest, _mock_async, db_session, tmp_path) -> None:
    from app.services.document_upload import IngestFailedError

    mock_ingest.return_value = Document(
        id=uuid.uuid4(),
        course_id="PPL",
        filename="empty.pdf",
        doc_kind="notes",
        status="failed",
        page_count=None,
        error_message="No text extracted from PDF",
    )

    with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
        with pytest.raises(IngestFailedError, match="No text extracted"):
            upload_and_ingest_document(
                db_session,
                course_id="PPL",
                filename="empty.pdf",
                content_type="application/pdf",
                data=b"%PDF-1.4",
                doc_kind="notes",
            )


@patch("app.main.upload_and_ingest_document")
def test_api_upload_async_returns_202(mock_upload) -> None:
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    mock_upload.return_value = {
        "document_id": doc_id,
        "course_id": "PPL",
        "filename": "async.pdf",
        "doc_kind": "notes",
        "status": "queued",
        "page_count": None,
        "upload_intent": "quick",
        "extraction_quality": {"upload_intent": "quick"},
        "job_id": job_id,
    }

    response = client.post(
        "/api/v1/courses/PPL/documents",
        files={"file": ("async.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "notes"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"] == job_id
    assert body["document_id"] == doc_id


@patch("app.main.upload_and_ingest_document")
def test_api_upload_returns_201(mock_upload) -> None:
    mock_upload.return_value = {
        "document_id": str(uuid.uuid4()),
        "course_id": "PPL",
        "filename": "PPL notes.pdf",
        "doc_kind": "notes",
        "status": "ready",
        "page_count": 94,
        "upload_intent": "quick",
        "extraction_quality": {"nonempty_pages": 90, "upload_intent": "quick"},
    }

    response = client.post(
        "/api/v1/courses/PPL/documents",
        files={"file": ("PPL notes.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "notes"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert body["course_id"] == "PPL"
    assert set(body.keys()) == {
        "document_id",
        "course_id",
        "filename",
        "doc_kind",
        "status",
        "page_count",
        "upload_intent",
        "extraction_quality",
    }
    assert body["upload_intent"] == "quick"


def test_api_upload_rejects_invalid_doc_kind() -> None:
    response = client.post(
        "/api/v1/courses/PPL/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "invalid"},
    )
    assert response.status_code == 400


def test_api_upload_rejects_non_pdf() -> None:
    response = client.post(
        "/api/v1/courses/PPL/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"doc_kind": "notes"},
    )
    assert response.status_code == 400


@patch("app.main.upload_and_ingest_document")
def test_api_upload_ingest_failure_422(mock_upload) -> None:
    from app.services.document_upload import IngestFailedError

    mock_upload.side_effect = IngestFailedError("No text extracted from PDF")

    response = client.post(
        "/api/v1/courses/PPL/documents",
        files={"file": ("empty.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "notes"},
    )
    assert response.status_code == 422
    assert "No text extracted" in response.json()["detail"]


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_api_upload_e2e_with_fixture(db_session, tmp_path) -> None:
    add_test_course(db_session, "PPL", "PPL")
    db_session.commit()
    with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
        with open(NOTES_PDF, "rb") as handle:
            response = client.post(
                "/api/v1/courses/PPL/documents",
                files={"file": (NOTES_PDF.name, handle, "application/pdf")},
                data={"doc_kind": "notes"},
            )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["page_count"] == 94
    assert body["filename"] == NOTES_PDF.name


@patch("app.main.run_study_query")
def test_query_still_works_after_upload_route_exists(mock_query, db_session) -> None:
    from app.services.rag.pipeline import StudyQueryResult

    add_test_course(db_session, "PPL", "PPL")
    db_session.commit()
    mock_query.return_value = StudyQueryResult(
        status="ok",
        answer="Answer.",
        sources=[],
        rerank_scores=[],
    )
    response = client.post(
        "/api/v1/query",
        json={"course_id": "PPL", "question": "What is a lexeme?", "preset": "study"},
    )
    assert response.status_code == 200
