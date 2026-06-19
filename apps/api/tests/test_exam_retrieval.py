"""Exam preset retrieval: past_paper only; study presets exclude past_paper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import settings
from app.services.rag.pipeline import run_study_question
from app.services.rag.retrieve import (
    EXAM_DOC_KINDS,
    STUDY_DOC_KINDS,
    _doc_filter_sql,
    _exam_doc_filter_sql,
    _study_doc_filter_sql,
    fetch_exam_candidates,
    fetch_hybrid_candidates,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"


def test_study_doc_filter_sql_excludes_past_paper() -> None:
    sql = _study_doc_filter_sql()
    assert "past_paper" not in sql
    for kind in STUDY_DOC_KINDS:
        assert f"'{kind}'" in sql


def test_exam_doc_filter_sql_past_paper_only() -> None:
    sql = _exam_doc_filter_sql()
    assert EXAM_DOC_KINDS == ("past_paper",)
    assert "'past_paper'" in sql
    assert "notes" not in sql
    assert "textbook" not in sql


def test_doc_filter_sql_scopes_kinds() -> None:
    study_sql = _doc_filter_sql(STUDY_DOC_KINDS)
    exam_sql = _doc_filter_sql(EXAM_DOC_KINDS)
    assert "'notes'" in study_sql and "'past_paper'" not in study_sql
    assert "'past_paper'" in exam_sql and "'notes'" not in exam_sql


@patch("app.services.rag.retrieve._count_exam_questions", return_value=0)
@patch("app.services.rag.retrieve._metadata_toc_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_focus_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_search", return_value=[])
@patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384])
@patch("app.services.rag.retrieve._vector_search")
def test_fetch_exam_candidates_passes_past_paper_doc_kinds(
    mock_vector,
    _mock_embed,
    _mock_bm25,
    _mock_focus,
    _mock_meta,
    _mock_count,
) -> None:
    mock_vector.return_value = []

    fetch_exam_candidates(None, course_id="PPL", question="lexemes")  # type: ignore[arg-type]

    assert mock_vector.call_args.kwargs["doc_kinds"] == EXAM_DOC_KINDS


@patch("app.services.rag.retrieve._metadata_toc_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_focus_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_search", return_value=[])
@patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384])
@patch("app.services.rag.retrieve._vector_search")
def test_fetch_hybrid_candidates_defaults_to_study_doc_kinds(
    mock_vector,
    _mock_embed,
    _mock_bm25,
    _mock_focus,
    _mock_meta,
) -> None:
    mock_vector.return_value = []

    fetch_hybrid_candidates(None, course_id="PPL", question="lexemes")  # type: ignore[arg-type]

    assert mock_vector.call_args.kwargs["doc_kinds"] == STUDY_DOC_KINDS


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_exam_retrieval_uses_past_paper_only(db_session) -> None:
    from app.services.ingestion import ingest_document

    papers_pdf = PAPERS_PDF
    if not papers_pdf.exists():
        pytest.skip("Missing past papers fixture")

    ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    ingest_document(db_session, file_path=papers_pdf, course_id="PPL", doc_kind="past_paper")
    db_session.commit()

    outcome = run_study_question(
        db_session,
        course_id="PPL",
        question="Questions on lexemes and tokens",
        preset="exam",
    )
    if outcome.status == "ok":
        assert outcome.chunks
        assert all(c.doc_kind == "past_paper" for c in outcome.chunks)
        assert all(c.doc_kind != "notes" for c in outcome.chunks)


@patch("app.services.rag.pipeline.apply_confidence_gate_detailed")
def test_exam_preset_uses_lower_gate_threshold(mock_gate) -> None:
    import uuid

    from app.services.rag.retrieve import RetrievedChunk

    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="past.pdf",
        doc_kind="past_paper",
        page=1,
        text="q",
        parent_text=None,
        rerank_score=0.3,
    )
    mock_gate.return_value = ([chunk], "ok", None)

    with patch("app.services.rag.pipeline.fetch_exam_candidates", return_value=[chunk]):
        with patch("app.services.rag.pipeline.rerank_chunks", return_value=[chunk]):
            with patch("app.services.rag.pipeline.expand_parent_context", return_value=[chunk]):
                from app.services.rag.pipeline import run_study_question

                run_study_question(None, "PPL", "lexemes", preset="exam")  # type: ignore[arg-type]

    assert mock_gate.call_args.kwargs["min_rerank_score"] == settings.min_rerank_score_exam


@patch("app.services.rag.pipeline.apply_confidence_gate_detailed")
def test_study_preset_uses_standard_gate_threshold(mock_gate) -> None:
    import uuid

    from app.services.rag.retrieve import RetrievedChunk

    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="notes.pdf",
        doc_kind="notes",
        page=1,
        text="q",
        parent_text=None,
        rerank_score=0.8,
    )
    mock_gate.return_value = ([chunk], "ok", None)

    with patch("app.services.rag.pipeline.fetch_hybrid_candidates", return_value=[chunk]):
        with patch("app.services.rag.pipeline.rerank_chunks", return_value=[chunk]):
            with patch("app.services.rag.pipeline.expand_parent_context", return_value=[chunk]):
                from app.services.rag.pipeline import run_study_question

                run_study_question(None, "PPL", "lexemes", preset="study")  # type: ignore[arg-type]

    assert mock_gate.call_args.kwargs["min_rerank_score"] == settings.min_rerank_score


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_exam_retrieval_not_in_materials_without_past_papers(db_session) -> None:
    from app.services.ingestion import ingest_document

    ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    db_session.commit()

    outcome = run_study_question(
        db_session,
        course_id="PPL",
        question="Questions on lexemes and tokens",
        preset="exam",
    )
    assert outcome.status == "not_in_materials"
    assert outcome.chunks == []
