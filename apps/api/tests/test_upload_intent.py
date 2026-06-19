"""Tests for upload_intent on document upload and ingest (SP-050c)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Course
from app.services.document_upload import (
    UploadValidationError,
    normalize_upload_intent,
    upload_and_ingest_document,
    validate_upload_intent,
)
from app.services.ingestion import ingest_document

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"

client = TestClient(app)


def test_normalize_upload_intent_defaults_to_quick() -> None:
    assert normalize_upload_intent(None) == "quick"
    assert normalize_upload_intent("") == "quick"
    assert normalize_upload_intent("topic") == "topic"


def test_validate_upload_intent_rejects_invalid() -> None:
    with pytest.raises(UploadValidationError, match="Invalid upload_intent"):
        validate_upload_intent(doc_kind="notes", upload_intent="exam")


def test_validate_upload_intent_past_paper_requires_past_paper() -> None:
    with pytest.raises(UploadValidationError, match="past_paper"):
        validate_upload_intent(doc_kind="past_paper", upload_intent="quick")


def test_validate_upload_intent_syllabus_requires_syllabus() -> None:
    with pytest.raises(UploadValidationError, match="syllabus"):
        validate_upload_intent(doc_kind="syllabus", upload_intent="quick")


@pytest.mark.parametrize(
    ("doc_kind", "upload_intent"),
    [
        ("notes", "quick"),
        ("notes", "topic"),
        ("notes", "syllabus"),
        ("textbook", "quick"),
        ("textbook", "topic"),
        ("textbook", "syllabus"),
        ("past_paper", "past_paper"),
        ("syllabus", "syllabus"),
    ],
)
def test_validate_upload_intent_allowed_pairs(doc_kind: str, upload_intent: str) -> None:
    validate_upload_intent(doc_kind=doc_kind, upload_intent=upload_intent)


def test_api_rejects_invalid_upload_intent() -> None:
    response = client.post(
        "/api/v1/courses/TEST/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "notes", "upload_intent": "invalid"},
    )
    assert response.status_code == 400
    assert "upload_intent" in response.json()["detail"]


def test_api_rejects_past_paper_intent_mismatch() -> None:
    response = client.post(
        "/api/v1/courses/TEST/documents",
        files={"file": ("paper.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "past_paper", "upload_intent": "quick"},
    )
    assert response.status_code == 400


@patch("app.main.upload_and_ingest_document")
def test_api_defaults_upload_intent_to_quick(mock_upload) -> None:
    mock_upload.return_value = {
        "document_id": str(uuid.uuid4()),
        "course_id": "CHEM",
        "filename": "notes.pdf",
        "doc_kind": "notes",
        "status": "ready",
        "page_count": 10,
        "upload_intent": "quick",
        "extraction_quality": {"upload_intent": "quick"},
    }

    response = client.post(
        "/api/v1/courses/CHEM/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
        data={"doc_kind": "notes"},
    )

    assert response.status_code == 201
    _, kwargs = mock_upload.call_args
    assert kwargs["upload_intent"] is None
    assert response.json()["upload_intent"] == "quick"


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_quick_notes_skips_outline_extract(db_session, tmp_path) -> None:
    with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
        with patch(
            "app.services.course_outline.maybe_extract_outline_on_notes_ingest"
        ) as mock_extract:
            doc = ingest_document(
                db_session,
                file_path=NOTES_PDF,
                course_id="QUICKTEST",
                doc_kind="notes",
                upload_intent="quick",
            )

    mock_extract.assert_not_called()
    course = db_session.get(Course, "QUICKTEST")
    assert course is not None
    assert course.outline_data is None
    assert doc.extraction_quality is not None
    assert doc.extraction_quality["upload_intent"] == "quick"


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_syllabus_intent_notes_runs_outline_extract(db_session, tmp_path) -> None:
    generic_pdf = tmp_path / "generic_notes.pdf"
    generic_pdf.write_bytes(NOTES_PDF.read_bytes())

    with patch(
        "app.services.course_outline.maybe_extract_outline_on_notes_ingest"
    ) as mock_extract:
        mock_extract.return_value = {"unit_count": 3, "source": "extracted"}
        doc = ingest_document(
            db_session,
            file_path=generic_pdf,
            course_id="SYLLTEST",
            doc_kind="notes",
            upload_intent="syllabus",
        )

    mock_extract.assert_called_once()
    assert doc.extraction_quality is not None
    assert doc.extraction_quality["upload_intent"] == "syllabus"
    assert doc.extraction_quality.get("outline", {}).get("unit_count") == 3


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_cli_ingest_without_upload_intent_still_extracts_outline(db_session, tmp_path) -> None:
    generic_pdf = tmp_path / "generic_notes.pdf"
    generic_pdf.write_bytes(NOTES_PDF.read_bytes())

    with patch(
        "app.services.course_outline.maybe_extract_outline_on_notes_ingest"
    ) as mock_extract:
        mock_extract.return_value = {"unit_count": 2}
        ingest_document(
            db_session,
            file_path=generic_pdf,
            course_id="CLITEST",
            doc_kind="notes",
        )

    mock_extract.assert_called_once()


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_ppl_fixture_outline_unchanged_with_quick_intent(db_session) -> None:
    doc = ingest_document(
        db_session,
        file_path=NOTES_PDF,
        course_id="PPL",
        doc_kind="notes",
        upload_intent="quick",
    )
    outline = (doc.extraction_quality or {}).get("outline") or {}
    assert outline.get("unit_count") == 5


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_upload_e2e_persists_upload_intent(db_session, tmp_path) -> None:
    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
            with open(NOTES_PDF, "rb") as handle:
                response = client.post(
                    "/api/v1/courses/CHEM050C/documents",
                    files={"file": (NOTES_PDF.name, handle, "application/pdf")},
                    data={"doc_kind": "notes", "upload_intent": "topic"},
                )
        assert response.status_code == 201
        body = response.json()
        assert body["upload_intent"] == "topic"
        assert body["extraction_quality"]["upload_intent"] == "topic"
    finally:
        app.dependency_overrides.clear()


@patch("app.services.document_upload.ingest_document")
def test_upload_and_ingest_passes_resolved_intent(mock_ingest, db_session, tmp_path) -> None:
    from app.models import Document

    mock_ingest.return_value = Document(
        id=uuid.uuid4(),
        course_id="CHEM",
        filename="notes.pdf",
        doc_kind="notes",
        status="ready",
        page_count=5,
        extraction_quality={"upload_intent": "topic"},
    )

    with patch("app.services.document_upload.UPLOAD_ROOT", tmp_path):
        upload_and_ingest_document(
            db_session,
            course_id="CHEM",
            filename="notes.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.4",
            doc_kind="notes",
            upload_intent="topic",
        )

    _, kwargs = mock_ingest.call_args
    assert kwargs["upload_intent"] == "topic"
