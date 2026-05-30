"""Tests for confidence gate refusal behavior."""

from __future__ import annotations

import uuid

from app.services.rag.gate import apply_confidence_gate
from app.services.rag.retrieve import RetrievedChunk


def _chunk(rerank_score: float | None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="PPL notes.pdf",
        doc_kind="notes",
        page=1,
        text="sample",
        parent_text=None,
        rerank_score=rerank_score,
    )


def test_gate_refuses_empty_chunks() -> None:
    chunks, status = apply_confidence_gate([], min_rerank_score=0.0)
    assert status == "not_in_materials"
    assert chunks == []


def test_gate_refuses_low_score() -> None:
    chunks, status = apply_confidence_gate([_chunk(0.1)], min_rerank_score=0.5)
    assert status == "not_in_materials"
    assert chunks == []


def test_gate_passes_above_threshold() -> None:
    chunks, status = apply_confidence_gate([_chunk(0.8)], min_rerank_score=0.5)
    assert status == "ok"
    assert len(chunks) == 1


def test_gate_refuses_none_score() -> None:
    chunks, status = apply_confidence_gate([_chunk(None)], min_rerank_score=0.0)
    assert status == "not_in_materials"
    assert chunks == []
