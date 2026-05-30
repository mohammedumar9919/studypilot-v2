"""Parent-context expansion for retrieved chunks."""

from __future__ import annotations

from app.config import settings
from app.services.rag.retrieve import RetrievedChunk


def expand_parent_context(
    chunks: list[RetrievedChunk],
    *,
    max_tokens: int | None = None,
) -> list[RetrievedChunk]:
    """
    Ensure parent text is attached and apply a simple token budget stub.

    Phase 1c will replace the char-based budget with tiktoken.
    """
    budget = max_tokens if max_tokens is not None else settings.context_max_tokens
    char_budget = budget * 4
    used = 0
    expanded: list[RetrievedChunk] = []

    for chunk in chunks:
        parent_text = chunk.parent_text
        if parent_text and used + len(parent_text) > char_budget:
            parent_text = parent_text[: max(0, char_budget - used)]
        if parent_text:
            used += len(parent_text)

        expanded.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                filename=chunk.filename,
                doc_kind=chunk.doc_kind,
                page=chunk.page,
                text=chunk.text,
                parent_text=parent_text,
                parent_id=chunk.parent_id,
                parent_page_start=chunk.parent_page_start,
                parent_page_end=chunk.parent_page_end,
                unit=chunk.unit,
                section_title=chunk.section_title,
                toc_path=chunk.toc_path,
                vector_score=chunk.vector_score,
                bm25_score=chunk.bm25_score,
                rrf_score=chunk.rrf_score,
                rerank_score=chunk.rerank_score,
            )
        )
    return expanded
