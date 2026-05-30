"""Tests for POST /api/v1/query/stream (SSE — mocked, no network)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.rag.pipeline import StudyQuestionResult
from app.services.rag.retrieve import RetrievedChunk

client = TestClient(app)


def _chunk() -> RetrievedChunk:
    doc_id = uuid.uuid4()
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        filename="PPL notes.pdf",
        doc_kind="notes",
        page=11,
        text="A lexeme is the abstract unit of meaning.",
        parent_text="Unit 2 vocabulary. A lexeme is the abstract unit of meaning.",
        rerank_score=0.82,
    )


def _parse_sse(body: str) -> list[dict]:
    """Parse SSE text into list of {event, data} dicts."""
    events: list[dict] = []
    current_event = "message"
    for line in body.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            payload = json.loads(line[len("data:") :].strip())
            events.append({"event": current_event, "data": payload})
            current_event = "message"
    return events


def _stream_query(**overrides) -> tuple[int, list[dict]]:
    payload = {
        "course_id": "PPL",
        "question": "What is a lexeme?",
        "preset": "study",
        "debug": False,
        **overrides,
    }
    with client.stream("POST", "/api/v1/query/stream", json=payload) as response:
        body = response.read().decode("utf-8")
        return response.status_code, _parse_sse(body)


@patch("app.main.run_study_question")
def test_stream_refusal_emits_single_done(mock_retrieval) -> None:
    mock_retrieval.return_value = StudyQuestionResult(
        status="not_in_materials",
        chunks=[],
        rerank_scores=[],
    )

    status_code, events = _stream_query()

    assert status_code == 200
    assert len(events) == 1
    assert events[0]["event"] == "done"
    assert events[0]["data"]["status"] == "not_in_materials"
    assert events[0]["data"]["answer"] is None
    assert events[0]["data"]["sources"] == []


@patch("app.main.stream_study_answer")
@patch("app.main.run_study_question")
def test_stream_ok_emits_retrieval_tokens_done(mock_retrieval, mock_stream) -> None:
    chunk = _chunk()
    mock_retrieval.return_value = StudyQuestionResult(
        status="ok",
        chunks=[chunk],
        rerank_scores=[0.82],
    )
    mock_stream.return_value = iter(["A ", "lexeme."])

    status_code, events = _stream_query()

    assert status_code == 200
    assert events[0]["event"] == "retrieval_complete"
    assert events[0]["data"]["chunk_count"] == 1
    assert len(events[0]["data"]["sources"]) == 1
    assert events[0]["data"]["rerank_scores"] == [0.82]

    token_events = [e for e in events if e["event"] == "token"]
    assert len(token_events) == 2
    assert token_events[0]["data"]["delta"] == "A "
    assert token_events[1]["data"]["delta"] == "lexeme."

    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["status"] == "ok"
    assert events[-1]["data"]["answer"] == "A lexeme."
    assert len(events[-1]["data"]["sources"]) == 1


@patch("app.main.stream_study_answer")
@patch("app.main.run_study_question")
def test_stream_debug_in_retrieval_complete(mock_retrieval, mock_stream) -> None:
    chunk = _chunk()
    mock_retrieval.return_value = StudyQuestionResult(
        status="ok",
        chunks=[chunk],
        rerank_scores=[0.9],
    )
    mock_stream.return_value = iter(["Answer"])

    _, events = _stream_query(debug=True)

    assert events[0]["event"] == "retrieval_complete"
    assert events[0]["data"]["retrieval_debug"] is not None
    assert events[0]["data"]["retrieval_debug"]["chunk_count"] == 1


def test_stream_rejects_unsupported_preset() -> None:
    response = client.post(
        "/api/v1/query/stream",
        json={
            "course_id": "PPL",
            "question": "What is a lexeme?",
            "preset": "flashcards",
        },
    )
    assert response.status_code == 400


@patch("app.services.rag.generate._stream_complete")
def test_stream_study_answer_yields_deltas(mock_stream_complete) -> None:
    mock_stream_complete.return_value = iter(["Hello", " world"])

    from app.services.rag.generate import stream_study_answer

    deltas = list(stream_study_answer("Q?", [_chunk()], preset="study"))
    assert deltas == ["Hello", " world"]


def test_format_sse_event() -> None:
    from app.services.rag.pipeline import format_sse_event

    text = format_sse_event("token", {"delta": "x"})
    assert text.startswith("event: token\n")
    assert 'data: {"delta": "x"}' in text
    assert text.endswith("\n\n")
