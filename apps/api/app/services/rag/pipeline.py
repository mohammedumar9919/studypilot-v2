"""Study-mode RAG orchestrator (retrieve → rerank → gate → context → generate)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.services.rag.context import expand_parent_context
from app.services.rag.gate import apply_confidence_gate
from app.services.rag.generate import _excerpt_text, chunks_to_sources, generate_study_answer
from app.services.rag.rerank import rerank_chunks
from app.services.rag.retrieve import RetrievedChunk, fetch_hybrid_candidates


@dataclass
class StudyQuestionResult:
    status: str
    chunks: list[RetrievedChunk]
    rerank_scores: list[float]


@dataclass
class StudyQueryResult:
    status: str
    answer: str | None
    sources: list[dict[str, Any]] = field(default_factory=list)
    rerank_scores: list[float] = field(default_factory=list)
    retrieval_debug: dict[str, Any] | None = None


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    """Format one Server-Sent Event frame (event + JSON data)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def run_study_question(
    session: Session,
    course_id: str,
    question: str,
    preset: str = "study",
) -> StudyQuestionResult:
    """
    Run the study retrieval pipeline without LLM generation.

    preset: only 'study' is supported in Phase 1b (excludes past_paper via doc_kind filter).
    """
    if preset != "study":
        raise ValueError(f"Unsupported preset: {preset}")

    candidates = fetch_hybrid_candidates(session, course_id=course_id, question=question)
    if not candidates:
        return StudyQuestionResult(status="not_in_materials", chunks=[], rerank_scores=[])

    reranked = rerank_chunks(
        question,
        candidates,
        top_k=settings.rerank_output_top_k,
    )
    gated, status = apply_confidence_gate(reranked)
    top_for_eval = gated[: settings.study_output_top_k]

    if status != "ok":
        return StudyQuestionResult(status="not_in_materials", chunks=[], rerank_scores=[])

    expanded = expand_parent_context(top_for_eval)
    scores = [c.rerank_score for c in expanded if c.rerank_score is not None]
    return StudyQuestionResult(status="ok", chunks=expanded, rerank_scores=scores)


def _build_retrieval_debug(chunks: list[RetrievedChunk], rerank_scores: list[float]) -> dict[str, Any]:
    return {
        "chunk_count": len(chunks),
        "pages": [c.page for c in chunks],
        "filenames": [c.filename for c in chunks],
        "rerank_scores": rerank_scores,
        "chunks": [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "filename": c.filename,
                "page": c.page,
                "rerank_score": c.rerank_score,
                "unit": c.unit,
                "section_title": c.section_title,
                "toc_path": c.toc_path,
                "excerpt": _excerpt_text(c, max_chars=300),
            }
            for c in chunks
        ],
    }


def run_study_query(
    session: Session,
    course_id: str,
    question: str,
    preset: str = "study",
    *,
    debug: bool = False,
) -> StudyQueryResult:
    """Full study pipeline: retrieval then OpenRouter generation."""
    if preset != "study":
        raise ValueError(f"Unsupported preset: {preset}")

    retrieval = run_study_question(session, course_id=course_id, question=question, preset=preset)
    if retrieval.status != "ok":
        return StudyQueryResult(
            status="not_in_materials",
            answer=None,
            sources=[],
            rerank_scores=[],
            retrieval_debug=None,
        )

    answer = generate_study_answer(question, retrieval.chunks, preset=preset)
    sources = chunks_to_sources(retrieval.chunks)
    retrieval_debug = (
        _build_retrieval_debug(retrieval.chunks, retrieval.rerank_scores) if debug else None
    )
    return StudyQueryResult(
        status="ok",
        answer=answer,
        sources=sources,
        rerank_scores=retrieval.rerank_scores,
        retrieval_debug=retrieval_debug,
    )
