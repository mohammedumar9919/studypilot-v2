"""Tests for GET /exam/analytics Tier 1 concept analytics (SP-060b)."""

from __future__ import annotations

import uuid

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Document, ExamConcept, ExamConceptAlias, ExamQuestion, ExamQuestionConcept
from app.services.exam.analytics import compute_exam_analytics
from app.services.exam.concept_derive import UNCLASSIFIED_LABEL
from tests.conftest import add_test_course

client = TestClient(app)


def _seed_analytics_fixture(db_session) -> None:
    add_test_course(db_session, "ANLY", "Analytics Test")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="ANLY",
            filename="papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=3,
        )
    )
    q1 = ExamQuestion(
        id=uuid.uuid4(),
        document_id=doc_id,
        course_id="ANLY",
        page=1,
        paper_label="July 2021 Main",
        prompt_text="Explain operator precedence and associativity.",
        marks=10,
        extraction_method="regex",
    )
    q2 = ExamQuestion(
        id=uuid.uuid4(),
        document_id=doc_id,
        course_id="ANLY",
        page=2,
        paper_label="July 2022 Main",
        prompt_text="Define operator precedence rules.",
        marks=2,
        extraction_method="regex",
    )
    q3 = ExamQuestion(
        id=uuid.uuid4(),
        document_id=doc_id,
        course_id="ANLY",
        page=3,
        paper_label="July 2022 Backlog",
        prompt_text="???",
        marks=2,
        extraction_method="regex",
    )
    db_session.add_all([q1, q2, q3])
    db_session.flush()

    concept_a = ExamConcept(
        course_id="ANLY",
        label="Operator Precedence",
        canonical_terms=["operator precedence"],
        confidence=0.9,
        is_unclassified=False,
    )
    concept_b = ExamConcept(
        course_id="ANLY",
        label="Operator Associativity",
        canonical_terms=["operator associativity"],
        confidence=0.8,
        is_unclassified=False,
    )
    unclassified = ExamConcept(
        course_id="ANLY",
        label=UNCLASSIFIED_LABEL,
        canonical_terms=[],
        confidence=0.0,
        is_unclassified=True,
    )
    db_session.add_all([concept_a, concept_b, unclassified])
    db_session.flush()

    db_session.add_all(
        [
            ExamConceptAlias(course_id="ANLY", alias="operator precedence", concept_id=concept_a.id),
            ExamConceptAlias(course_id="ANLY", alias="operator associativity", concept_id=concept_b.id),
            ExamQuestionConcept(question_id=q1.id, concept_id=concept_a.id, weight=1.0),
            ExamQuestionConcept(question_id=q1.id, concept_id=concept_b.id, weight=0.5),
            ExamQuestionConcept(question_id=q2.id, concept_id=concept_a.id, weight=1.0),
            ExamQuestionConcept(question_id=q3.id, concept_id=unclassified.id, weight=1.0),
        ]
    )
    db_session.commit()


def test_analytics_empty_course_not_ready(db_session) -> None:
    add_test_course(db_session, "EMPTY", "Empty")
    db_session.commit()

    result = compute_exam_analytics(db_session, "EMPTY")
    assert result["analytics_ready"] is False
    assert result["concepts"] == []
    assert result["summary"]["question_count"] == 0
    assert result["predictions"]["items"] == []
    assert result["predictions"]["formula_version"] == "v1"


def test_analytics_fixture_counts_weightage_and_multilabel(db_session) -> None:
    _seed_analytics_fixture(db_session)

    result = compute_exam_analytics(db_session, "ANLY")
    assert result["analytics_ready"] is True
    assert result["summary"]["question_count"] == 3
    assert result["summary"]["classified_concept_count"] == 2
    assert result["summary"]["unclassified_only_questions"] == 1
    assert result["summary"]["total_marks"] == 14
    assert result["summary"]["distinct_papers"] == 3

    top = result["concepts"][0]
    assert top["label"] == "Operator Precedence"
    assert top["unique_question_count"] == 2
    assert top["question_count"] == 2.0
    assert top["marks_total"] == 12.0
    assert top["weightage_pct"] == pytest.approx(85.71, abs=0.1)
    assert top["long_count"] == 1
    assert top["short_count"] == 1
    assert top["paper_reach"] == 2
    assert top["trend_slope"] is not None

    predictions = result["predictions"]
    assert predictions["formula_version"] == "v1"
    assert predictions["top_n"] == 10
    assert len(predictions["items"]) >= 1
    assert predictions["items"][0]["label"] == "Operator Precedence"
    assert predictions["items"][0]["rank"] == 1
    assert "score" in predictions["items"][0]
    assert isinstance(predictions["items"][0]["reasons"], list)


def test_analytics_excludes_unclassified_by_default(db_session) -> None:
    _seed_analytics_fixture(db_session)

    result = compute_exam_analytics(db_session, "ANLY", include_unclassified=False)
    labels = [row["label"] for row in result["concepts"]]
    assert UNCLASSIFIED_LABEL not in labels
    assert result["summary"]["unclassified_only_questions"] == 1


def test_analytics_include_unclassified_when_requested(db_session) -> None:
    _seed_analytics_fixture(db_session)

    result = compute_exam_analytics(db_session, "ANLY", include_unclassified=True)
    labels = [row["label"] for row in result["concepts"]]
    assert UNCLASSIFIED_LABEL in labels


def test_analytics_pagination_and_sort(db_session) -> None:
    _seed_analytics_fixture(db_session)

    by_label = compute_exam_analytics(db_session, "ANLY", sort="label_asc", limit=1, offset=0)
    assert len(by_label["concepts"]) == 1
    assert by_label["pagination"]["total"] == 2
    assert by_label["concepts"][0]["label"] == "Operator Associativity"

    page_two = compute_exam_analytics(db_session, "ANLY", sort="label_asc", limit=1, offset=1)
    assert page_two["concepts"][0]["rank"] == 2


def test_analytics_api_unknown_course_404(db_session) -> None:
    response = client.get("/api/v1/courses/NOPE/exam/analytics")
    assert response.status_code == 404


def test_analytics_api_route_returns_ready_payload(db_session) -> None:
    _seed_analytics_fixture(db_session)

    def override_session() -> Generator:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.get("/api/v1/courses/ANLY/exam/analytics?limit=10")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body["analytics_ready"] is True
    assert body["tier"] == 1
    assert len(body["concepts"]) >= 2
    assert "predictions" in body
    assert body["predictions"]["formula_version"] == "v1"
    assert len(body["predictions"]["items"]) >= 1


@pytest.mark.skip(reason="PPL corpus not loaded in isolated test DB")
def test_ppl_analytics_smoke(db_session) -> None:
    from app.models import ExamQuestion
    from app.services.exam.concept_derive import derive_exam_concepts_for_course

    if db_session.query(ExamQuestion).filter_by(course_id="PPL").count() == 0:
        pytest.skip("PPL exam_questions not present in test DB")

    derive_exam_concepts_for_course(db_session, "PPL")
    db_session.commit()

    result = compute_exam_analytics(db_session, "PPL", limit=5)
    if not result["analytics_ready"]:
        pytest.skip("PPL analytics not ready")

    assert result["summary"]["question_count"] > 0
    assert result["summary"]["concept_count"] > 0
    assert len(result["concepts"]) <= 5
    assert all(row["label"] for row in result["concepts"])
