"""Study-mode RAG orchestrator (retrieve → rerank → gate → context → generate)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.services.rag.context import expand_parent_context
from app.services.rag.gate import apply_confidence_gate_detailed
from app.services.rag.generate import _excerpt_text, chunks_to_sources, generate_study_answer, validate_preset
from app.services.rag.rerank import rerank_chunks
from app.services.rag.retrieve import (
    RetrievedChunk,
    fetch_exam_candidates,
    fetch_hybrid_candidates,
    get_exam_question_hits,
    retrieval_course_context,
)


@dataclass
class StudyQuestionResult:
    status: str
    chunks: list[RetrievedChunk]
    rerank_scores: list[float]
    refusal_reason: str | None = None
    top_rerank_score: float | None = None
    exam_question_hits: list[dict[str, Any]] | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)


def _gate_threshold(preset: str) -> float:
    if preset == "exam":
        return settings.min_rerank_score_exam
    return settings.min_rerank_score


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


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _retrieval_timeout_exceeded(pipeline_start: float) -> bool:
    if not settings.retrieval_timeout_enabled():
        return False
    return (time.perf_counter() - pipeline_start) >= settings.studypilot_retrieval_timeout_s


def _timeout_result(
    timings_ms: dict[str, float],
    *,
    exam_question_hits: list[dict[str, Any]] | None = None,
) -> StudyQuestionResult:
    timings_ms["total_retrieval_ms"] = round(sum(timings_ms.values()), 2)
    return StudyQuestionResult(
        status="not_in_materials",
        chunks=[],
        rerank_scores=[],
        refusal_reason="retrieval_timeout",
        exam_question_hits=exam_question_hits,
        timings_ms=timings_ms,
    )


def run_study_question(
    session: Session,
    course_id: str,
    question: str,
    preset: str = "study",
    source_ids: list[uuid.UUID] | None = None,
    topic_ids: list[uuid.UUID] | None = None,
) -> StudyQuestionResult:
    """
    Run the study retrieval pipeline without LLM generation.

    Study presets (study, summary, flashcards) retrieve notes/textbook/syllabus only.
    Exam preset retrieves past_paper documents only.
    """
    validate_preset(preset)
    pipeline_start = time.perf_counter()
    timings_ms: dict[str, float] = {}
    exam_question_hits: list[dict[str, Any]] | None = None

    with retrieval_course_context(course_id):
        retrieve_start = time.perf_counter()
        if preset == "exam":
            candidates = fetch_exam_candidates(
                session,
                course_id=course_id,
                question=question,
                document_ids=source_ids,
            )
            exam_question_hits = get_exam_question_hits()
        else:
            candidates = fetch_hybrid_candidates(
                session,
                course_id=course_id,
                question=question,
                document_ids=source_ids,
                topic_ids=topic_ids,
            )
        timings_ms["retrieve_ms"] = _elapsed_ms(retrieve_start)

        if _retrieval_timeout_exceeded(pipeline_start):
            return _timeout_result(timings_ms, exam_question_hits=exam_question_hits)

        if not candidates:
            timings_ms["total_retrieval_ms"] = round(sum(timings_ms.values()), 2)
            return StudyQuestionResult(
                status="not_in_materials",
                chunks=[],
                rerank_scores=[],
                refusal_reason="empty_corpus",
                exam_question_hits=exam_question_hits,
                timings_ms=timings_ms,
            )

        rerank_start = time.perf_counter()
        reranked = rerank_chunks(
            question,
            candidates,
            top_k=settings.rerank_output_top_k,
        )
        timings_ms["rerank_ms"] = _elapsed_ms(rerank_start)

        if _retrieval_timeout_exceeded(pipeline_start):
            return _timeout_result(timings_ms, exam_question_hits=exam_question_hits)

        gate_start = time.perf_counter()
        top_rerank = reranked[0].rerank_score if reranked else None
        gated, status, refusal_reason = apply_confidence_gate_detailed(
            reranked,
            min_rerank_score=_gate_threshold(preset),
        )
        timings_ms["gate_ms"] = _elapsed_ms(gate_start)

        if _retrieval_timeout_exceeded(pipeline_start):
            return _timeout_result(timings_ms, exam_question_hits=exam_question_hits)

        top_for_eval = gated[: settings.study_output_top_k]

        if status != "ok":
            timings_ms["total_retrieval_ms"] = round(sum(timings_ms.values()), 2)
            return StudyQuestionResult(
                status="not_in_materials",
                chunks=[],
                rerank_scores=[],
                refusal_reason=refusal_reason,
                top_rerank_score=top_rerank,
                exam_question_hits=exam_question_hits,
                timings_ms=timings_ms,
            )

        expand_start = time.perf_counter()
        expanded = expand_parent_context(top_for_eval)
        timings_ms["expand_ms"] = _elapsed_ms(expand_start)
        timings_ms["total_retrieval_ms"] = round(sum(timings_ms.values()), 2)

        if _retrieval_timeout_exceeded(pipeline_start):
            return _timeout_result(timings_ms, exam_question_hits=exam_question_hits)

        scores = [c.rerank_score for c in expanded if c.rerank_score is not None]
        return StudyQuestionResult(
            status="ok",
            chunks=expanded,
            rerank_scores=scores,
            exam_question_hits=exam_question_hits,
            timings_ms=timings_ms,
        )


def _build_retrieval_debug(
    chunks: list[RetrievedChunk],
    rerank_scores: list[float],
    *,
    exam_question_hits: list[dict[str, Any]] | None = None,
    timings_ms: dict[str, float] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
    if exam_question_hits:
        payload["exam_question_hits"] = exam_question_hits
    if timings_ms:
        payload["timings_ms"] = timings_ms
    return payload


def run_study_query(
    session: Session,
    course_id: str,
    question: str,
    preset: str = "study",
    *,
    debug: bool = False,
    source_ids: list[uuid.UUID] | None = None,
    topic_ids: list[uuid.UUID] | None = None,
) -> StudyQueryResult:
    """Full query pipeline: retrieval then OpenRouter generation."""
    validate_preset(preset)
    query_start = time.perf_counter()

    retrieval = run_study_question(
        session,
        course_id=course_id,
        question=question,
        preset=preset,
        source_ids=source_ids,
        topic_ids=topic_ids,
    )
    timings_ms = dict(retrieval.timings_ms)

    if retrieval.status != "ok":
        retrieval_debug = None
        if debug:
            retrieval_debug = {
                "refusal_reason": retrieval.refusal_reason,
                "top_rerank_score": retrieval.top_rerank_score,
            }
            if timings_ms:
                retrieval_debug["timings_ms"] = timings_ms
        return StudyQueryResult(
            status="not_in_materials",
            answer=None,
            sources=[],
            rerank_scores=[],
            retrieval_debug=retrieval_debug,
        )

    generate_start = time.perf_counter()
    answer = generate_study_answer(question, retrieval.chunks, preset=preset)
    timings_ms["generate_ms"] = _elapsed_ms(generate_start)
    timings_ms["total_ms"] = _elapsed_ms(query_start)

    sources = chunks_to_sources(retrieval.chunks)
    retrieval_debug = (
        _build_retrieval_debug(
            retrieval.chunks,
            retrieval.rerank_scores,
            exam_question_hits=retrieval.exam_question_hits,
            timings_ms=timings_ms,
        )
        if debug
        else None
    )
    return StudyQueryResult(
        status="ok",
        answer=answer,
        sources=sources,
        rerank_scores=retrieval.rerank_scores,
        retrieval_debug=retrieval_debug,
    )
