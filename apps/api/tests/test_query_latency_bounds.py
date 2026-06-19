"""Tests for SP-004a query latency bounds (pipeline timings + optional retrieval timeout)."""

from __future__ import annotations

import time
import uuid
from unittest.mock import patch

import pytest

from app.config import settings
from app.services.rag.pipeline import (
    _build_retrieval_debug,
    run_study_question,
    run_study_query,
)
from app.services.rag.retrieve import RetrievedChunk


def _sample_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        document_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        filename="notes.pdf",
        doc_kind="notes",
        page=1,
        text="Lexeme definition text.",
        parent_text="Parent context for lexeme.",
        rerank_score=0.9,
        unit="Unit 1",
        section_title="Intro",
        toc_path="Unit 1 > Intro",
    )


def test_retrieval_timeout_disabled_by_default() -> None:
    assert settings.retrieval_timeout_enabled() is False


def test_build_retrieval_debug_includes_timings_ms() -> None:
    debug = _build_retrieval_debug(
        [_sample_chunk()],
        [0.9],
        timings_ms={"retrieve_ms": 12.5, "rerank_ms": 40.0, "total_ms": 52.5},
    )
    assert debug["timings_ms"]["retrieve_ms"] == 12.5
    assert debug["timings_ms"]["total_ms"] == 52.5


@patch("app.services.rag.pipeline.fetch_hybrid_candidates")
@patch("app.services.rag.pipeline.rerank_chunks")
@patch("app.services.rag.pipeline.apply_confidence_gate_detailed")
@patch("app.services.rag.pipeline.expand_parent_context")
def test_run_study_question_records_timings_ms(
    mock_expand,
    mock_gate,
    mock_rerank,
    mock_fetch,
    db_session,
) -> None:
    chunk = _sample_chunk()
    mock_fetch.return_value = [chunk]
    mock_rerank.return_value = [chunk]
    mock_gate.return_value = ([chunk], "ok", None)
    mock_expand.return_value = [chunk]

    result = run_study_question(db_session, "PPL", "What is a lexeme?")

    assert result.status == "ok"
    assert result.timings_ms["retrieve_ms"] >= 0
    assert result.timings_ms["rerank_ms"] >= 0
    assert result.timings_ms["gate_ms"] >= 0
    assert result.timings_ms["expand_ms"] >= 0
    assert result.timings_ms["total_retrieval_ms"] >= 0


@patch("app.services.rag.pipeline.fetch_hybrid_candidates")
def test_retrieval_timeout_refuses_when_exceeded(mock_fetch, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "studypilot_retrieval_timeout_s", 0.001)

    def slow_fetch(*_args, **_kwargs):
        time.sleep(0.02)
        return [_sample_chunk()]

    mock_fetch.side_effect = slow_fetch

    result = run_study_question(db_session, "PPL", "What is a lexeme?")

    assert result.status == "not_in_materials"
    assert result.refusal_reason == "retrieval_timeout"
    assert "retrieve_ms" in result.timings_ms


@patch("app.services.rag.pipeline.generate_study_answer", return_value="A lexeme is a word.")
@patch("app.services.rag.pipeline.fetch_hybrid_candidates")
@patch("app.services.rag.pipeline.rerank_chunks")
@patch("app.services.rag.pipeline.apply_confidence_gate_detailed")
@patch("app.services.rag.pipeline.expand_parent_context")
def test_run_study_query_debug_includes_timings_ms(
    mock_expand,
    mock_gate,
    mock_rerank,
    mock_fetch,
    _mock_generate,
    db_session,
) -> None:
    chunk = _sample_chunk()
    mock_fetch.return_value = [chunk]
    mock_rerank.return_value = [chunk]
    mock_gate.return_value = ([chunk], "ok", None)
    mock_expand.return_value = [chunk]

    result = run_study_query(
        db_session,
        "PPL",
        "What is a lexeme?",
        debug=True,
    )

    assert result.status == "ok"
    assert result.retrieval_debug is not None
    timings = result.retrieval_debug["timings_ms"]
    assert "retrieve_ms" in timings
    assert "generate_ms" in timings
    assert "total_ms" in timings
