"""Confidence gate — refuse low-confidence retrieval before LLM."""

from __future__ import annotations

from app.config import settings
from app.services.rag.retrieve import RetrievedChunk


def apply_confidence_gate(
    chunks: list[RetrievedChunk],
    *,
    min_rerank_score: float | None = None,
) -> tuple[list[RetrievedChunk], str]:
    """Return (chunks, status) where status is 'ok' or 'not_in_materials'."""
    threshold = settings.min_rerank_score if min_rerank_score is None else min_rerank_score
    if not chunks:
        return [], "not_in_materials"

    top_score = chunks[0].rerank_score
    if top_score is None or top_score < threshold:
        return [], "not_in_materials"

    return chunks, "ok"
