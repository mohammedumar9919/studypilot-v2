"""Confidence gate — refuse low-confidence retrieval before LLM."""

from __future__ import annotations

from typing import Literal

from app.config import settings
from app.services.rag.retrieve import RetrievedChunk

RefusalReason = Literal["empty_corpus", "below_threshold"]


def apply_confidence_gate_detailed(
    chunks: list[RetrievedChunk],
    *,
    min_rerank_score: float | None = None,
) -> tuple[list[RetrievedChunk], str, RefusalReason | None]:
    """Return (chunks, status, refusal_reason). status is 'ok' or 'not_in_materials'."""
    threshold = settings.min_rerank_score if min_rerank_score is None else min_rerank_score
    if not chunks:
        return [], "not_in_materials", "empty_corpus"

    top_score = chunks[0].rerank_score
    if top_score is None or top_score < threshold:
        return [], "not_in_materials", "below_threshold"

    return chunks, "ok", None


def apply_confidence_gate(
    chunks: list[RetrievedChunk],
    *,
    min_rerank_score: float | None = None,
) -> tuple[list[RetrievedChunk], str]:
    """Return (chunks, status) where status is 'ok' or 'not_in_materials'."""
    gated, status, _ = apply_confidence_gate_detailed(chunks, min_rerank_score=min_rerank_score)
    return gated, status
