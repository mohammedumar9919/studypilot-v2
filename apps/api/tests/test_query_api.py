"""Tests for POST /api/v1/query (mocked generation — no network)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from tests.conftest import add_test_course
from fastapi.testclient import TestClient

from app.main import app
from app.services.rag.pipeline import StudyQueryResult, StudyQuestionResult
from app.services.rag.retrieve import RetrievedChunk

client = TestClient(app)


def _chunk(
    *,
    unit: str | None = None,
    section_title: str | None = None,
    toc_path: str | None = None,
) -> RetrievedChunk:
    doc_id = uuid.uuid4()
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        filename="PPL notes.pdf",
        doc_kind="notes",
        page=11,
        text="A lexeme is the abstract unit of meaning.",
        parent_text="Unit 2 vocabulary. A lexeme is the abstract unit of meaning.",
        unit=unit,
        section_title=section_title,
        toc_path=toc_path,
        rerank_score=0.82,
    )


@patch("app.main.run_study_query")
def test_query_refusal_skips_llm(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(
        status="not_in_materials",
        answer=None,
        sources=[],
        rerank_scores=[],
        retrieval_debug=None,
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "Explain photosynthesis in plants.",
            "preset": "study",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_in_materials"
    assert body["answer"] is None
    assert body["sources"] == []
    assert body["rerank_scores"] == []
    assert body["retrieval_debug"] is None
    mock_run.assert_called_once()


@patch("app.main.run_study_query")
def test_query_ok_returns_contract_shape(mock_run) -> None:
    chunk = _chunk()
    mock_run.return_value = StudyQueryResult(
        status="ok",
        answer="A lexeme is the abstract linguistic unit. [PPL notes.pdf p.11]",
        sources=[
            {
                "document_id": str(chunk.document_id),
                "filename": chunk.filename,
                "page": chunk.page,
                "excerpt": chunk.text,
            }
        ],
        rerank_scores=[0.82, 0.71],
        retrieval_debug=None,
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "study",
            "debug": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["answer"], str) and body["answer"]
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert set(source.keys()) == {"document_id", "filename", "page", "excerpt"}
    assert source["filename"] == "PPL notes.pdf"
    assert source["page"] == 11
    assert body["rerank_scores"] == [0.82, 0.71]
    assert body["retrieval_debug"] is None


@patch("app.main.run_study_query")
def test_query_debug_includes_retrieval_debug(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(
        status="ok",
        answer="Answer text.",
        sources=[],
        rerank_scores=[0.9],
        retrieval_debug={"chunk_count": 1, "pages": [11]},
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "study",
            "debug": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_debug"] == {"chunk_count": 1, "pages": [11]}
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["debug"] is True


def test_build_retrieval_debug_includes_outline_metadata() -> None:
    from app.services.rag.pipeline import _build_retrieval_debug

    chunk = _chunk(
        unit="unit-2",
        section_title="Lexemes and Tokens",
        toc_path="Unit 2 > 2.3 Lexemes",
    )
    debug = _build_retrieval_debug([chunk], [0.82])
    entry = debug["chunks"][0]

    assert entry["unit"] == "unit-2"
    assert entry["section_title"] == "Lexemes and Tokens"
    assert entry["toc_path"] == "Unit 2 > 2.3 Lexemes"
    assert entry["excerpt"]
    assert "lexeme" in entry["excerpt"].lower()


@patch("app.services.rag.pipeline.generate_study_answer")
@patch("app.services.rag.pipeline.run_study_question")
def test_run_study_query_debug_chunks_include_outline(
    mock_retrieval,
    mock_generate,
    db_session,
) -> None:
    chunk = _chunk(
        unit="unit-2",
        section_title="Lexemes and Tokens",
        toc_path="Unit 2 > 2.3 Lexemes",
    )
    mock_retrieval.return_value = StudyQuestionResult(
        status="ok",
        chunks=[chunk],
        rerank_scores=[0.82],
    )
    mock_generate.return_value = "Answer."

    from app.services.rag.pipeline import run_study_query

    result = run_study_query(
        db_session,
        course_id="PPL",
        question="What is a lexeme?",
        preset="study",
        debug=True,
    )

    assert result.retrieval_debug is not None
    entry = result.retrieval_debug["chunks"][0]
    assert entry["unit"] == "unit-2"
    assert entry["section_title"] == "Lexemes and Tokens"
    assert entry["toc_path"] == "Unit 2 > 2.3 Lexemes"
    assert entry["excerpt"]


def test_query_rejects_unsupported_preset() -> None:
    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "not-a-preset",
        },
    )
    assert response.status_code == 400


@patch("app.main.run_study_query")
def test_query_omitted_source_ids_unchanged(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(
        status="not_in_materials",
        answer=None,
        sources=[],
        rerank_scores=[],
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "study",
        },
    )

    assert response.status_code == 200
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["source_ids"] is None
    assert mock_run.call_args.kwargs["topic_ids"] is None


@patch("app.main.run_study_query")
def test_query_passes_validated_source_ids(mock_run, db_session) -> None:
    from app.database import get_session
    from app.models import Course, Document

    add_test_course(db_session, "PPL", "Programming Languages")
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

    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    mock_run.return_value = StudyQueryResult(
        status="not_in_materials",
        answer=None,
        sources=[],
        rerank_scores=[],
    )
    try:
        response = client.post(
            "/api/v1/query",
            json={
                "course_id": "PPL",
                "question": "What is a lexeme?",
                "preset": "study",
                "source_ids": [str(doc_id)],
            },
        )
        assert response.status_code == 200
        assert mock_run.call_args.kwargs["source_ids"] == [doc_id]
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_query_rejects_empty_source_ids(db_session) -> None:
    from app.database import get_session
    from app.models import Course

    add_test_course(db_session, "PPL", "Programming Languages")
    db_session.commit()

    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.post(
            "/api/v1/query",
            json={
                "course_id": "PPL",
                "question": "What is a lexeme?",
                "preset": "study",
                "source_ids": [],
            },
        )
        assert response.status_code == 400
        assert "must not be empty" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_query_rejects_empty_topic_ids(db_session) -> None:
    from app.database import get_session
    from app.models import Course

    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    db_session.commit()

    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = client.post(
            "/api/v1/query",
            json={
                "course_id": "CHEM",
                "question": "Explain entropy",
                "preset": "study",
                "topic_ids": [],
            },
        )
        assert response.status_code == 400
        assert "must not be empty" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)


@patch("app.services.rag.pipeline.generate_study_answer")
@patch("app.services.rag.pipeline.run_study_question")
def test_pipeline_refusal_does_not_call_generate(mock_retrieval, mock_generate, db_session) -> None:
    mock_retrieval.return_value = StudyQuestionResult(
        status="not_in_materials",
        chunks=[],
        rerank_scores=[],
    )

    from app.services.rag.pipeline import run_study_query

    result = run_study_query(
        db_session,
        course_id="PPL",
        question="Explain photosynthesis.",
        preset="study",
    )

    assert result.status == "not_in_materials"
    assert result.answer is None
    mock_generate.assert_not_called()
