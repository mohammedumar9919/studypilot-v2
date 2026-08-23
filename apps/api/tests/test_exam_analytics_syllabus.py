"""Tests for syllabus-primary exam analytics (SP-061c)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import get_session
from app.main import app
from app.models import Document, ExamQuestion
from app.services.exam.analytics import compute_exam_analytics
from app.services.exam.analytics_syllabus import build_syllabus_primary_analytics
from tests.conftest import add_test_course

client = TestClient(app)


def _seed_syllabus_fixture(db_session) -> None:
    add_test_course(db_session, "SYLB", "Syllabus Primary Test")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="SYLB",
            filename="papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=2,
        )
    )
    paper = "Sep/Oct 2023 | E-5616/N/BL | 2023"
    rows = [
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="SYLB",
            page=1,
            paper_label=paper,
            question_number="1a",
            prompt_text="Explain Nernst equation.",
            marks=2,
            unit="Unit I",
            section_title="Electrochemistry",
            extraction_method="regex",
        ),
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="SYLB",
            page=1,
            paper_label=paper,
            question_number="1b",
            prompt_text="Define reference electrode.",
            marks=2,
            unit="Unit I",
            section_title="Electrochemistry",
            extraction_method="regex",
        ),
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="SYLB",
            page=2,
            paper_label=paper,
            question_number="11",
            prompt_text="Discuss battery chemistry in detail.",
            marks=10,
            unit="Unit I",
            section_title="Battery Chemistry",
            extraction_method="regex",
        ),
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="SYLB",
            page=2,
            paper_label=paper,
            question_number="12a",
            prompt_text="EDTA hardness method.",
            marks=2,
            unit="Unit II",
            section_title="Water Chemistry",
            extraction_method="regex",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()


def test_build_syllabus_primary_analytics_counts(db_session) -> None:
    _seed_syllabus_fixture(db_session)
    questions = list(db_session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == "SYLB")))
    block = build_syllabus_primary_analytics(db_session, "SYLB", questions)
    assert block["primary"] == "syllabus"
    assert block["summary"]["paper_count"] == 1
    assert block["summary"]["subpart_count"] == 3
    assert block["summary"]["main_question_count"] == 2
    assert block["summary"]["years"] == ["2023"]
    units = {row["unit"]: row for row in block["units"]}
    assert units["Unit I"]["subpart_count"] == 2
    assert units["Unit II"]["subpart_count"] == 1


def test_compute_exam_analytics_primary_auto_hides_flat(db_session) -> None:
    _seed_syllabus_fixture(db_session)
    payload = compute_exam_analytics(db_session, "SYLB", primary="auto", include_flat=False)
    assert payload["analytics_ready"] is True
    assert "syllabus_primary" in payload
    assert payload["syllabus_primary"]["summary"]["subpart_count"] == 3
    assert payload["concepts"] == []
    assert payload["pagination"]["flat_hidden"] is True


def test_compute_exam_analytics_include_flat(db_session) -> None:
    _seed_syllabus_fixture(db_session)
    payload = compute_exam_analytics(db_session, "SYLB", primary="auto", include_flat=True)
    assert payload["analytics_ready"] is True
    assert "syllabus_primary" in payload
    assert len(payload["concepts"]) >= 0
    assert payload["pagination"].get("flat_hidden") is not True


def test_exam_analytics_route_primary_params(db_session) -> None:
    _seed_syllabus_fixture(db_session)

    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.get(
            "/api/v1/courses/SYLB/exam/analytics",
            params={"primary": "syllabus", "include_flat": "false"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["syllabus_primary"]["summary"]["subpart_count"] == 3
        assert body["concepts"] == []
    finally:
        app.dependency_overrides.pop(get_session, None)
