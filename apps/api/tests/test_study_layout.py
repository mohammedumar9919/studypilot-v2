"""Tests for GET /api/v1/courses/{course_id}/study-layout."""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import Course, Document, StudyTopic
from app.services.study_layout import build_sidebar_views, get_study_layout, resolve_study_layout_mode
from tests.conftest import add_test_course

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def test_resolve_mode_ppl_case_insensitive() -> None:
    assert resolve_study_layout_mode("PPL") == "mapped"
    assert resolve_study_layout_mode("ppl") == "mapped"
    assert resolve_study_layout_mode("Ppl") == "mapped"


def test_resolve_mode_corpus_for_generic_course() -> None:
    assert resolve_study_layout_mode("CHEM") == "corpus"
    assert resolve_study_layout_mode("TEST101") == "corpus"


def test_get_study_layout_unknown_course(db_session) -> None:
    assert get_study_layout(db_session, "UNKNOWN") is None


def test_get_study_layout_sources_ready_and_processing_only(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    ready_id = uuid.uuid4()
    processing_id = uuid.uuid4()
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
                id=processing_id,
                course_id="CHEM",
                filename="textbook.pdf",
                doc_kind="textbook",
                status="processing",
                page_count=None,
            ),
            Document(
                id=uuid.uuid4(),
                course_id="CHEM",
                filename="failed.pdf",
                doc_kind="notes",
                status="failed",
                page_count=10,
            ),
            Document(
                id=uuid.uuid4(),
                course_id="CHEM",
                filename="pending.pdf",
                doc_kind="syllabus",
                status="pending",
            ),
        ]
    )
    db_session.commit()

    result = get_study_layout(db_session, "CHEM")
    assert result is not None
    assert result["mode"] == "corpus"
    assert result["structure_mode"] == "corpus"
    assert result["course_id"] == "CHEM"
    assert len(result["sources"]) == 2
    assert result["sources"][0]["document_id"] == str(ready_id)
    assert result["sources"][0]["filename"] == "notes.pdf"
    assert result["sources"][0]["page_count"] == 42
    assert result["sources"][0]["status"] == "ready"
    assert result["sources"][0]["doc_kind"] == "notes"
    assert result["sources"][1]["document_id"] == str(processing_id)
    assert result["sources"][1]["status"] == "processing"
    assert result["sources"][1]["page_count"] is None
    assert result["sidebar_views"] == {"sources": True, "topics": False, "course_map": True}
    assert result["outline_available"] is True


def test_api_study_layout_ppl_mapped(db_session) -> None:
    add_test_course(db_session, "PPL", "Programming Languages", structure_mode="mapped")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="PPL",
            filename="PPL notes.pdf",
            doc_kind="notes",
            status="ready",
            page_count=94,
        )
    )
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/PPL/study-layout")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "mapped"
        assert body["structure_mode"] == "mapped"
        assert body["course_id"] == "PPL"
        assert len(body["sources"]) == 1
        assert body["sources"][0]["document_id"] == str(doc_id)
        assert body["sources"][0]["filename"] == "PPL notes.pdf"
        assert body["sources"][0]["page_count"] == 94
        assert body["sidebar_views"] == {"sources": False, "topics": False, "course_map": True}
        assert body["outline_available"] is True
    finally:
        _clear_db_override()


def test_api_study_layout_chem_corpus(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.add(
        Document(
            id=uuid.uuid4(),
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
        response = client.get("/api/v1/courses/CHEM/study-layout")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "corpus"
        assert body["course_id"] == "CHEM"
        assert len(body["sources"]) == 1
        assert body["sources"][0]["doc_kind"] == "notes"
        assert body["sidebar_views"] == {"sources": True, "topics": False, "course_map": True}
        assert body["outline_available"] is True
    finally:
        _clear_db_override()


def test_api_study_layout_empty_sources(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/CHEM/study-layout")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "corpus"
        assert body["sources"] == []
        assert body["sidebar_views"] == {"sources": False, "topics": False, "course_map": False}
        assert body["outline_available"] is False
    finally:
        _clear_db_override()


def test_api_study_layout_404(db_session) -> None:
    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/UNKNOWN/study-layout")
        assert response.status_code == 404
    finally:
        _clear_db_override()


def test_sidebar_views_organized_without_topics(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    db_session.commit()

    layout = get_study_layout(db_session, "CHEM")
    assert layout is not None
    assert layout["sidebar_views"]["topics"] is True
    assert layout["sidebar_views"]["sources"] is False
    assert layout["sidebar_views"]["course_map"] is False


def test_sidebar_views_corpus_with_study_topics(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.add(
        StudyTopic(id=uuid.uuid4(), course_id="CHEM", title="Thermodynamics", sort_order=0)
    )
    db_session.commit()

    layout = get_study_layout(db_session, "CHEM")
    assert layout is not None
    assert layout["sidebar_views"]["topics"] is True
    assert layout["sidebar_views"]["sources"] is False


def test_sidebar_views_course_map_from_stored_outline(db_session) -> None:
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={
            "outline_source": "uploaded",
            "outline_quality": "high",
            "units": [{"id": "1", "title": "Unit 1", "page_start": 0, "page_end": 9}],
        },
    )
    db_session.commit()

    layout = get_study_layout(db_session, "CHEM")
    assert layout is not None
    assert layout["sidebar_views"]["course_map"] is True
    assert layout["outline_available"] is True


def test_build_sidebar_views_ppl_fixture() -> None:
    course = Course(id="PPL", name="PPL", structure_mode="mapped")
    views = build_sidebar_views(
        "PPL",
        course,
        structure_mode="mapped",
        documents=[Document(id=uuid.uuid4(), course_id="PPL", filename="notes.pdf", status="ready")],
        topics=[StudyTopic(id=uuid.uuid4(), course_id="PPL", title="Topic", sort_order=0)],
        outline_available=True,
    )
    assert views == {"sources": False, "topics": False, "course_map": True}
