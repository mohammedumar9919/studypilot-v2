"""Tests for GET /api/v1/courses/{course_id}/documents."""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import add_test_course

from app.database import get_session
from app.main import app
from app.models import Course, Document
from app.services.course_documents import get_course_documents

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def test_get_course_documents_unknown_course(db_session) -> None:
    assert get_course_documents(db_session, "UNKNOWN") is None


def test_get_course_documents_ready_and_processing_only(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry")
    ready_id = uuid.uuid4()
    db_session.add_all(
        [
            Document(
                id=ready_id,
                course_id="CHEM",
                filename="notes.pdf",
                doc_kind="notes",
                status="ready",
                page_count=42,
            ),
            Document(
                id=uuid.uuid4(),
                course_id="CHEM",
                filename="failed.pdf",
                doc_kind="notes",
                status="failed",
            ),
        ]
    )
    db_session.commit()

    result = get_course_documents(db_session, "CHEM")
    assert result is not None
    assert result["course_id"] == "CHEM"
    assert len(result["documents"]) == 1
    assert result["documents"][0]["document_id"] == str(ready_id)
    assert result["documents"][0]["page_count"] == 42


def test_api_course_documents(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="CHEM",
            filename="Chemistry notes.pdf",
            doc_kind="notes",
            status="ready",
            page_count=25,
        )
    )
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/CHEM/documents")
        assert response.status_code == 200
        body = response.json()
        assert body["course_id"] == "CHEM"
        assert len(body["documents"]) == 1
        assert body["documents"][0]["document_id"] == str(doc_id)
        assert body["documents"][0]["doc_kind"] == "notes"
    finally:
        _clear_db_override()


def test_api_course_documents_404(db_session) -> None:
    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/UNKNOWN/documents")
        assert response.status_code == 404
    finally:
        _clear_db_override()
