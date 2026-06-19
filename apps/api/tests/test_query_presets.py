"""Tests for query preset routing (study, summary, flashcards, exam)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.rag.pipeline import StudyQueryResult, StudyQuestionResult
from app.services.rag.retrieve import RetrievedChunk

client = TestClient(app)


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="PPL notes.pdf",
        doc_kind="notes",
        page=11,
        text="A lexeme is the abstract unit of meaning.",
        parent_text="Unit 2 vocabulary.",
        rerank_score=0.82,
    )


@patch("app.main.run_study_query")
def test_query_summary_preset(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(
        status="ok",
        answer="- Lexeme: abstract unit\n- Token: category of lexemes",
        sources=[],
        rerank_scores=[0.9],
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "Summarize lexemes and tokens",
            "preset": "summary",
        },
    )

    assert response.status_code == 200
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["preset"] == "summary"


@patch("app.main.run_study_query")
def test_query_flashcards_preset(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(
        status="ok",
        answer="**Q:** What is a lexeme?\n**A:** An abstract linguistic unit.",
        sources=[],
        rerank_scores=[0.9],
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "Lexemes and tokens",
            "preset": "flashcards",
        },
    )

    assert response.status_code == 200
    assert mock_run.call_args.kwargs["preset"] == "flashcards"


def _past_paper_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="PPL previous papers.pdf",
        doc_kind="past_paper",
        page=3,
        text="Question 2: Define lexeme and token.",
        parent_text="Past paper section on lexemes.",
        rerank_score=0.85,
    )


@patch("app.main.run_study_query")
def test_query_exam_preset(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(
        status="ok",
        answer="Similar past questions on lexemes appear in [PPL previous papers.pdf p.3].",
        sources=[],
        rerank_scores=[0.85],
    )

    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "Questions on lexemes and tokens",
            "preset": "exam",
        },
    )

    assert response.status_code == 200
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["preset"] == "exam"


def test_query_rejects_unknown_preset() -> None:
    response = client.post(
        "/api/v1/query",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "invalid_preset",
        },
    )
    assert response.status_code == 400


@patch("app.main.stream_study_answer")
@patch("app.main.run_study_question")
def test_stream_summary_preset(mock_retrieval, mock_stream) -> None:
    mock_retrieval.return_value = StudyQuestionResult(
        status="ok",
        chunks=[_chunk()],
        rerank_scores=[0.82],
    )
    mock_stream.return_value = iter(["- Point one"])

    with client.stream(
        "POST",
        "/api/v1/query/stream",
        json={
            "course_id": "PPL",
            "question": "Summarize lexemes",
            "preset": "summary",
        },
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "retrieval_complete" in body
    assert "token" in body
    mock_stream.assert_called_once()
    assert mock_stream.call_args.kwargs["preset"] == "summary"


@patch("app.main.stream_study_answer")
@patch("app.main.run_study_question")
def test_stream_exam_preset(mock_retrieval, mock_stream) -> None:
    mock_retrieval.return_value = StudyQuestionResult(
        status="ok",
        chunks=[_past_paper_chunk()],
        rerank_scores=[0.85],
    )
    mock_stream.return_value = iter(["Past paper excerpt on lexemes."])

    with client.stream(
        "POST",
        "/api/v1/query/stream",
        json={
            "course_id": "PPL",
            "question": "Questions on lexemes and tokens",
            "preset": "exam",
        },
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "retrieval_complete" in body
    assert "token" in body
    mock_stream.assert_called_once()
    assert mock_stream.call_args.kwargs["preset"] == "exam"


def test_stream_rejects_unknown_preset() -> None:
    response = client.post(
        "/api/v1/query/stream",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "invalid_preset",
        },
    )
    assert response.status_code == 400
