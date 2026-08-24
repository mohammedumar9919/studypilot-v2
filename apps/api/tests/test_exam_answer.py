"""Tests for POST /exam/answer answer-on-tap (SP-060d)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import Document, ExamConcept, ExamConceptAlias, ExamQuestion, ExamQuestionConcept
from app.services.exam.exam_answer import build_concept_study_query, marks_to_budget
from app.services.rag.pipeline import StudyQuestionResult
from app.services.rag.retrieve import RetrievedChunk
from tests.conftest import add_test_course

client = TestClient(app)


@contextmanager
def _override_db(db_session: Session) -> Generator[None, None, None]:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_answer_fixture(db_session) -> tuple[ExamConcept, ExamQuestion, uuid.UUID, uuid.UUID]:
    add_test_course(db_session, "ANSR", "Answer Test")
    notes_id = uuid.uuid4()
    textbook_id = uuid.uuid4()
    past_id = uuid.uuid4()
    db_session.add_all(
        [
            Document(
                id=notes_id,
                course_id="ANSR",
                filename="notes.pdf",
                doc_kind="notes",
                status="ready",
                page_count=5,
            ),
            Document(
                id=textbook_id,
                course_id="ANSR",
                filename="textbook.pdf",
                doc_kind="textbook",
                status="ready",
                page_count=10,
            ),
            Document(
                id=past_id,
                course_id="ANSR",
                filename="papers.pdf",
                doc_kind="past_paper",
                status="ready",
                page_count=3,
            ),
        ]
    )
    concept = ExamConcept(
        id=uuid.uuid4(),
        course_id="ANSR",
        label="Operator Precedence",
        canonical_terms=["operator precedence"],
        confidence=0.9,
        is_unclassified=False,
    )
    question = ExamQuestion(
        id=uuid.uuid4(),
        document_id=past_id,
        course_id="ANSR",
        page=1,
        paper_label="July 2024",
        prompt_text="Explain operator precedence in detail.",
        marks=10,
        extraction_method="regex",
    )
    db_session.add_all([concept, question])
    db_session.commit()
    return concept, question, notes_id, textbook_id


def test_marks_to_budget_mapping() -> None:
    assert marks_to_budget(10) == ("quality", "long")
    assert marks_to_budget(8) == ("quality", "long")
    assert marks_to_budget(7) == ("balanced", "medium")
    assert marks_to_budget(4) == ("balanced", "medium")
    assert marks_to_budget(2) == ("budget", "short")
    assert marks_to_budget(None) == ("budget", "short")


def test_concept_study_query_uses_label_and_aliases_not_exam_stem() -> None:
    concept = ExamConcept(
        course_id="ANSR",
        label="conducting polymers",
        canonical_terms=["conducting polymer", "electroactive polymers"],
    )
    concept.aliases = []
    query = build_concept_study_query(concept)
    short = build_concept_study_query(concept, short=True)
    exam_stem = "Write a short note on conducting polymers from the 2023 paper."
    assert query.startswith("Explain conducting polymers")
    assert "also: conducting polymer, electroactive polymers" in query
    assert "Use course notes and syllabus." in query
    assert exam_stem not in query
    assert query != exam_stem
    assert short == "Explain conducting polymers. Use course notes and syllabus."
    assert "also:" not in short


def test_tier1_no_study_docs(db_session) -> None:
    add_test_course(db_session, "EMPTY", "Empty Study Docs")
    past_id = uuid.uuid4()
    db_session.add(
        Document(
            id=past_id,
            course_id="EMPTY",
            filename="papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=1,
        )
    )
    concept = ExamConcept(
        id=uuid.uuid4(),
        course_id="EMPTY",
        label="Pointers",
        canonical_terms=["pointers"],
        confidence=0.8,
        is_unclassified=False,
    )
    db_session.add(concept)
    db_session.commit()

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/EMPTY/exam/answer",
            json={"concept_id": str(concept.id)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answers_available"] is False
    assert payload["status"] == "no_study_docs"
    assert payload["tier"] == 1
    assert payload["answer"] is None


@patch("app.services.exam.exam_answer.generate_study_answer", return_value="Grounded answer.")
@patch("app.services.exam.exam_answer.run_study_question")
def test_concept_tap_uses_study_preset(
    mock_run: object,
    mock_generate: object,
    db_session,
) -> None:
    concept, _, notes_id, _ = _seed_answer_fixture(db_session)
    hit_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=notes_id,
        filename="notes.pdf",
        doc_kind="notes",
        page=1,
        text="Precedence rules apply left-to-right.",
        parent_text=None,
        rerank_score=0.55,
    )
    mock_run.return_value = StudyQuestionResult(status="ok", chunks=[hit_chunk], rerank_scores=[0.55])

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(concept.id)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["target_type"] == "concept"
    assert payload["answers_available"] is True
    assert payload["answer"] == "Grounded answer."
    assert mock_run.call_args.kwargs["preset"] == "study"
    assert mock_run.call_args.kwargs["preset"] != "exam"


@patch("app.services.exam.exam_answer.generate_study_answer", return_value="Long answer.")
@patch("app.services.exam.exam_answer.run_study_question")
def test_question_marks_pass_quality_budget(
    mock_run: object,
    mock_generate: object,
    db_session,
) -> None:
    _, question, notes_id, _ = _seed_answer_fixture(db_session)
    hit_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=notes_id,
        filename="notes.pdf",
        doc_kind="notes",
        page=1,
        text="Detailed precedence explanation.",
        parent_text=None,
        rerank_score=0.62,
    )
    mock_run.return_value = StudyQuestionResult(status="ok", chunks=[hit_chunk], rerank_scores=[0.62])

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"question_id": str(question.id)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_length"] == "long"
    assert mock_generate.call_args.kwargs["llm_budget_tier"] == "quality"


@patch("app.services.exam.exam_answer.generate_study_answer")
@patch("app.services.exam.exam_answer.run_study_question")
def test_coverage_hit_miss(
    mock_run: object,
    mock_generate: object,
    db_session,
) -> None:
    concept, _, notes_id, textbook_id = _seed_answer_fixture(db_session)
    hit_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=notes_id,
        filename="notes.pdf",
        doc_kind="notes",
        page=2,
        text="Coverage sample.",
        parent_text=None,
        rerank_score=0.41,
    )
    mock_run.return_value = StudyQuestionResult(status="ok", chunks=[hit_chunk], rerank_scores=[0.41])
    mock_generate.return_value = "Answer."

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(concept.id)},
        )
    coverage = response.json()["coverage"]
    assert coverage["hit_count"] == 1
    assert coverage["miss_count"] == 1
    by_id = {row["document_id"]: row for row in coverage["documents"]}
    assert by_id[str(notes_id)]["status"] == "hit"
    assert by_id[str(textbook_id)]["status"] == "miss"


def test_bad_concept_id_returns_404(db_session) -> None:
    _seed_answer_fixture(db_session)
    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(uuid.uuid4())},
        )
    assert response.status_code == 404


def test_both_targets_rejected(db_session) -> None:
    concept, question, _, _ = _seed_answer_fixture(db_session)
    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(concept.id), "question_id": str(question.id)},
        )
    assert response.status_code == 422


@patch("app.services.exam.exam_answer.generate_study_answer", return_value="Grounded answer.")
@patch("app.services.exam.exam_answer.run_study_question")
def test_concept_tap_query_contains_label_not_only_exam_stem(
    mock_run: object,
    mock_generate: object,
    db_session,
) -> None:
    concept, question, notes_id, _ = _seed_answer_fixture(db_session)
    db_session.add(
        ExamQuestionConcept(
            question_id=question.id,
            concept_id=concept.id,
            weight=1.0,
        )
    )
    db_session.commit()

    hit_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=notes_id,
        filename="notes.pdf",
        doc_kind="notes",
        page=1,
        text="Precedence rules apply left-to-right.",
        parent_text=None,
        rerank_score=0.55,
    )
    mock_run.return_value = StudyQuestionResult(status="ok", chunks=[hit_chunk], rerank_scores=[0.55])

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(concept.id)},
        )
    assert response.status_code == 200
    payload = response.json()
    query_text = payload["query_text"]
    exam_stem = question.prompt_text.strip()
    assert concept.label in query_text
    assert query_text.startswith(f"Explain {concept.label}")
    assert "Use course notes and syllabus." in query_text
    assert query_text != exam_stem
    assert exam_stem not in query_text
    assert payload["answer_length"] == "long"
    assert mock_run.call_args.kwargs["preset"] == "study"
    assert mock_run.call_args.args[2] == query_text


@patch("app.services.exam.exam_answer.generate_study_answer", return_value="Retry answer.")
@patch("app.services.exam.exam_answer.run_study_question")
def test_concept_tap_retries_label_only_when_first_refused(
    mock_run: object,
    mock_generate: object,
    db_session,
) -> None:
    concept, _, notes_id, _ = _seed_answer_fixture(db_session)
    db_session.add(
        ExamConceptAlias(
            course_id="ANSR",
            alias="operator associativity",
            concept_id=concept.id,
        )
    )
    db_session.commit()

    hit_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=notes_id,
        filename="notes.pdf",
        doc_kind="notes",
        page=1,
        text="Precedence rules apply left-to-right.",
        parent_text=None,
        rerank_score=0.55,
    )
    mock_run.side_effect = [
        StudyQuestionResult(
            status="not_in_materials",
            chunks=[],
            rerank_scores=[],
            refusal_reason="below_threshold",
            top_rerank_score=0.12,
        ),
        StudyQuestionResult(status="ok", chunks=[hit_chunk], rerank_scores=[0.55]),
    ]

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(concept.id)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert mock_run.call_count == 2
    first_query = mock_run.call_args_list[0].args[2]
    retry_query = mock_run.call_args_list[1].args[2]
    assert concept.label in first_query
    assert "also:" in first_query
    assert retry_query == f"Explain {concept.label}. Use course notes and syllabus."
    assert "also:" not in retry_query
    assert mock_run.call_args_list[0].kwargs["preset"] == "study"
    assert mock_run.call_args_list[1].kwargs["preset"] == "study"


@patch("app.services.exam.exam_answer.run_study_question")
def test_gate_refusal_includes_debug_fields(mock_run: object, db_session) -> None:
    concept, _, _, _ = _seed_answer_fixture(db_session)
    mock_run.return_value = StudyQuestionResult(
        status="not_in_materials",
        chunks=[],
        rerank_scores=[],
        refusal_reason="below_threshold",
        top_rerank_score=0.12,
    )

    with _override_db(db_session):
        response = client.post(
            "/api/v1/courses/ANSR/exam/answer",
            json={"concept_id": str(concept.id)},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_in_materials"
    assert payload["refusal_reason"] == "below_threshold"
    assert payload["top_rerank_score"] == 0.12
