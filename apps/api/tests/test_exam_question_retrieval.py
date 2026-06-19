"""Exam preset retrieval over parsed exam_questions (SP-042b)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models import Chunk, ChunkEmbedding, ChunkParent, Course, Document, ExamQuestion
from app.services.rag.pipeline import run_study_query, run_study_question
from app.services.exam.topic_frequency import count_parsed_questions
from app.services.rag.retrieve import fetch_exam_candidates, get_exam_question_hits

from tests.conftest import add_test_course

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "eval" / "fixtures" / "ppl"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"

_READABLE_PAST_PAPER_TEXT = (
    "Question on Denotational Semantics and programming language concepts for the exam. " * 3
)


def _seed_past_paper_with_questions(
    db_session,
    *,
    course_id: str = "EXAM042",
    prompt_text: str = "Explain Denotational Semantics basic concept",
) -> uuid.UUID:
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    add_test_course(db_session, course_id, "Exam Truth Test")
    db_session.add(
        Document(
            id=doc_id,
            course_id=course_id,
            filename="past.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=5,
        )
    )
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=3,
            page_end=3,
            text=_READABLE_PAST_PAPER_TEXT,
        )
    )
    db_session.add(
        Chunk(
            id=chunk_id,
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=0,
            page=3,
            text=_READABLE_PAST_PAPER_TEXT,
            token_count=40,
        )
    )
    db_session.add(
        ChunkEmbedding(
            chunk_id=chunk_id,
            embedding=[0.1] * 384,
            embedding_model="test",
            dimensions=384,
        )
    )
    db_session.add(
        ExamQuestion(
            document_id=doc_id,
            course_id=course_id,
            page=3,
            part="A",
            question_number="2",
            prompt_text=prompt_text,
            unit="1",
            section_title="Syntax and Semantics",
            extraction_method="regex",
        )
    )
    db_session.commit()
    return doc_id


def test_fetch_exam_candidates_uses_question_path_when_rows_exist(db_session) -> None:
    _seed_past_paper_with_questions(db_session)
    assert count_parsed_questions(db_session, "EXAM042") == 1

    candidates = fetch_exam_candidates(
        db_session,
        course_id="EXAM042",
        question="Denotational Semantics basic concept",
    )
    hits = get_exam_question_hits()

    assert candidates
    assert all(candidate.doc_kind == "past_paper" for candidate in candidates)
    assert hits is not None
    assert len(hits) >= 1
    assert hits[0]["page"] == 3
    assert "Denotational" in hits[0]["prompt_snippet"]


def test_fetch_exam_candidates_without_questions_unchanged(db_session) -> None:
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    add_test_course(db_session, "LEGACY", "Legacy")
    db_session.add(
        Document(
            id=doc_id,
            course_id="LEGACY",
            filename="past.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=3,
        )
    )
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=1,
            page_end=1,
            text=_READABLE_PAST_PAPER_TEXT,
        )
    )
    db_session.add(
        Chunk(
            id=chunk_id,
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=0,
            page=1,
            text=_READABLE_PAST_PAPER_TEXT,
            token_count=20,
        )
    )
    db_session.add(
        ChunkEmbedding(
            chunk_id=chunk_id,
            embedding=[0.1] * 384,
            embedding_model="test",
            dimensions=384,
        )
    )
    db_session.commit()

    assert count_parsed_questions(db_session, "LEGACY") == 0
    with patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384]):
        candidates = fetch_exam_candidates(
            db_session,
            course_id="LEGACY",
            question="lexemes and tokens",
        )

    assert get_exam_question_hits() is None
    assert candidates
    assert candidates[0].doc_kind == "past_paper"


def test_exam_query_with_parsed_questions_returns_past_paper_sources(db_session) -> None:
    _seed_past_paper_with_questions(db_session)

    outcome = run_study_question(
        db_session,
        course_id="EXAM042",
        question="Denotational Semantics basic concept",
        preset="exam",
    )

    assert outcome.status == "ok"
    assert outcome.chunks
    assert all(chunk.doc_kind == "past_paper" for chunk in outcome.chunks)
    assert outcome.exam_question_hits
    assert outcome.exam_question_hits[0]["question_number"] == "2"


@patch("app.services.rag.pipeline.generate_study_answer", return_value="Similar past question.")
def test_exam_query_debug_includes_exam_question_hits(mock_generate, db_session) -> None:
    _seed_past_paper_with_questions(db_session)

    result = run_study_query(
        db_session,
        course_id="EXAM042",
        question="Denotational Semantics basic concept",
        preset="exam",
        debug=True,
    )

    assert result.status == "ok"
    assert result.retrieval_debug is not None
    assert result.retrieval_debug.get("exam_question_hits")
    assert result.sources
    assert all(source["filename"] == "past.pdf" for source in result.sources)


@pytest.mark.skipif(not PAPERS_PDF.exists(), reason="PPL past papers fixture missing")
def test_ingested_ppl_exam_query_uses_parsed_questions(db_session) -> None:
    from app.services.ingestion import ingest_document

    ingest_document(
        db_session,
        file_path=PAPERS_PDF,
        course_id="PPL042",
        doc_kind="past_paper",
    )
    db_session.commit()

    assert count_parsed_questions(db_session, "PPL042") > 0

    outcome = run_study_question(
        db_session,
        course_id="PPL042",
        question="Denotational Semantics basic concept",
        preset="exam",
    )

    if outcome.status == "ok":
        assert outcome.chunks
        assert all(chunk.doc_kind == "past_paper" for chunk in outcome.chunks)
        assert outcome.exam_question_hits
