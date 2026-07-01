"""Tests for Tier 3 exam analytics structure mapping (SP-060c)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Course, Document, ExamConcept, ExamConceptAlias, ExamQuestion, ExamQuestionConcept
from app.services.course_structure import confirm_course_structure
from app.services.exam.analytics import compute_exam_analytics
from app.services.exam.analytics_structure import auto_map_concepts_to_nodes, is_tier3_eligible
from app.services.exam.concept_derive import UNCLASSIFIED_LABEL
from tests.conftest import add_test_course

client = TestClient(app)


def _seed_mapped_structure_course(db_session) -> None:
    add_test_course(db_session, "DS", "Data Science", structure_mode="mapped")
    confirm_course_structure(
        db_session,
        "DS",
        [
            {
                "title": "UNIT-I Data Science",
                "subtopics": ["Linear Algebra for data science", "Dimensionality reduction"],
            },
            {
                "title": "UNIT IV R Programming",
                "subtopics": ["Introduction to R Programming", "Data frames"],
            },
        ],
    )
    course = db_session.get(Course, "DS")
    assert course is not None
    course.structure_mode = "mapped"
    db_session.flush()

    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="DS",
            filename="ds-pyq.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=2,
        )
    )
    q1 = ExamQuestion(
        id=uuid.uuid4(),
        document_id=doc_id,
        course_id="DS",
        page=1,
        paper_label="July 2023",
        prompt_text="Explain linear algebra for data science.",
        marks=10,
        extraction_method="regex",
    )
    q2 = ExamQuestion(
        id=uuid.uuid4(),
        document_id=doc_id,
        course_id="DS",
        page=2,
        paper_label="July 2023",
        prompt_text="Describe data frames in R.",
        marks=2,
        extraction_method="regex",
    )
    db_session.add_all([q1, q2])

    concept_algebra = ExamConcept(
        course_id="DS",
        label="linear algebra for data science",
        canonical_terms=["linear algebra"],
        is_unclassified=False,
    )
    concept_r = ExamConcept(
        course_id="DS",
        label="data frames",
        canonical_terms=["data frames in r"],
        is_unclassified=False,
    )
    concept_noise = ExamConcept(
        course_id="DS",
        label="quantum entanglement",
        canonical_terms=["quantum"],
        is_unclassified=False,
    )
    unclassified = ExamConcept(
        course_id="DS",
        label=UNCLASSIFIED_LABEL,
        canonical_terms=[],
        is_unclassified=True,
    )
    db_session.add_all([concept_algebra, concept_r, concept_noise, unclassified])
    db_session.flush()

    db_session.add_all(
        [
            ExamConceptAlias(course_id="DS", alias="linear algebra", concept_id=concept_algebra.id),
            ExamQuestionConcept(question_id=q1.id, concept_id=concept_algebra.id, weight=1.0),
            ExamQuestionConcept(question_id=q2.id, concept_id=concept_r.id, weight=1.0),
        ]
    )
    db_session.commit()


def test_tier1_when_no_structure(db_session) -> None:
    add_test_course(db_session, "CORPUS", "Corpus Only", structure_mode="corpus")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="CORPUS",
            filename="pyq.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=1,
        )
    )
    db_session.add(
        ExamQuestion(
            document_id=doc_id,
            course_id="CORPUS",
            page=1,
            prompt_text="Define polymorphism.",
            extraction_method="regex",
        )
    )
    concept = ExamConcept(
        course_id="CORPUS",
        label="Polymorphism",
        canonical_terms=["polymorphism"],
        is_unclassified=False,
    )
    db_session.add(concept)
    db_session.flush()
    db_session.add(
        ExamQuestionConcept(
            question_id=db_session.query(ExamQuestion).filter_by(course_id="CORPUS").one().id,
            concept_id=concept.id,
            weight=1.0,
        )
    )
    db_session.commit()

    result = compute_exam_analytics(db_session, "CORPUS", include_structure="auto")
    assert result["tier"] == 1
    assert "structure" not in result


def test_tier3_structure_rollup_and_unmapped(db_session) -> None:
    _seed_mapped_structure_course(db_session)

    assert is_tier3_eligible(db_session, "DS") is True

    result = compute_exam_analytics(db_session, "DS", include_structure="true")
    assert result["tier"] == 3
    assert result["structure"]["structure_mode"] == "mapped"
    assert len(result["structure"]["units"]) == 2

    unit_one = result["structure"]["units"][0]
    assert unit_one["title"].startswith("UNIT-I")
    assert unit_one["unique_question_count"] >= 1
    assert unit_one["subtopics"][0]["unique_question_count"] >= 1

    unit_four = result["structure"]["units"][1]
    assert "R Programming" in unit_four["title"]
    assert unit_four["unique_question_count"] >= 1

    unmapped_labels = {row["label"] for row in result["unmapped_concepts"]}
    assert "quantum entanglement" in unmapped_labels


def test_include_structure_false_keeps_tier1(db_session) -> None:
    _seed_mapped_structure_course(db_session)

    result = compute_exam_analytics(db_session, "DS", include_structure="false")
    assert result["tier"] == 1
    assert "structure" not in result


def test_zero_question_nodes_included(db_session) -> None:
    _seed_mapped_structure_course(db_session)

    result = compute_exam_analytics(db_session, "DS", include_structure="true")
    dimensionality = next(
        subtopic
        for unit in result["structure"]["units"]
        for subtopic in unit["subtopics"]
        if subtopic["title"] == "Dimensionality reduction"
    )
    assert dimensionality["unique_question_count"] == 0
    assert dimensionality["weightage_pct"] == 0.0


def test_analytics_api_tier3_route(db_session) -> None:
    _seed_mapped_structure_course(db_session)

    def override_session() -> Generator:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.get("/api/v1/courses/DS/exam/analytics?include_structure=true")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == 3
    assert "structure" in body
    assert "unmapped_concepts" in body


@patch("app.services.exam.analytics_structure.embed_texts")
def test_auto_map_prefers_subtopic_substring(mock_embed, db_session) -> None:
    from app.services.exam.analytics_structure import _build_structure_nodes

    mock_embed.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]

    structure = {
        "course_id": "X",
        "units": [
            {
                "id": str(uuid.uuid4()),
                "title": "UNIT-I Data Science",
                "subtopics": [
                    {"id": str(uuid.uuid4()), "title": "Linear Algebra for data science"},
                ],
            }
        ],
    }
    nodes, _ = _build_structure_nodes(structure)
    concept = ExamConcept(
        course_id="X",
        label="linear algebra for data science",
        canonical_terms=["linear algebra"],
        is_unclassified=False,
    )
    concept.aliases = []

    assignments, unmapped = auto_map_concepts_to_nodes([concept], nodes)
    assert unmapped == []
    assert sum(len(ids) for ids in assignments.values()) == 1
