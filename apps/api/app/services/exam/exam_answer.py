"""Exam answer-on-tap — study-lane RAG only (SP-060d)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, CoursePart, CourseSubtopic, CourseUnit, Document, ExamConcept, ExamQuestion, ExamQuestionConcept
from app.services.course_documents import list_course_documents
from app.services.course_structure import expand_structure_scope_to_document_ids
from app.services.exam.analytics_structure import is_tier3_eligible
from app.services.rag.generate import chunks_to_sources, generate_study_answer
from app.services.rag.pipeline import run_study_question
from app.services.rag.retrieve import STUDY_DOC_KINDS

STUDY_DOC_KIND_SET = set(STUDY_DOC_KINDS)


def marks_to_budget(marks: int | None) -> tuple[str, str]:
    """Map exam question marks to LLM budget tier and answer length label."""
    if marks is not None and marks >= 8:
        return "quality", "long"
    if marks is not None and marks >= 4:
        return "balanced", "medium"
    return "budget", "short"


def _list_ready_study_documents(session: Session, course_id: str) -> list[Document]:
    return [
        document
        for document in list_course_documents(session, course_id)
        if document.doc_kind in STUDY_DOC_KIND_SET and document.status == "ready"
    ]


def _resolve_answer_tier(session: Session, course_id: str, *, has_study_docs: bool) -> int:
    if not has_study_docs:
        return 1
    if is_tier3_eligible(session, course_id):
        return 3
    return 2


def _resolve_structure_scope_document_ids(
    session: Session,
    course_id: str,
    structure_node_id: uuid.UUID,
) -> list[uuid.UUID] | None:
    subtopic = session.get(CourseSubtopic, structure_node_id)
    if subtopic is not None and subtopic.unit.course_id == course_id:
        return expand_structure_scope_to_document_ids(session, subtopic_ids=[structure_node_id])

    part = session.get(CoursePart, structure_node_id)
    if part is not None and part.unit.course_id == course_id:
        return expand_structure_scope_to_document_ids(session, part_ids=[structure_node_id])

    unit = session.get(CourseUnit, structure_node_id)
    if unit is not None and unit.course_id == course_id:
        return expand_structure_scope_to_document_ids(session, unit_ids=[structure_node_id])

    raise LookupError(f"Structure node not found for course: {structure_node_id}")


def _build_coverage(
    study_documents: list[Document],
    chunks: list,
) -> dict[str, Any]:
    hit_scores: dict[str, float] = {}
    for chunk in chunks:
        doc_id = str(chunk.document_id)
        score = float(chunk.rerank_score or 0.0)
        hit_scores[doc_id] = max(hit_scores.get(doc_id, 0.0), score)

    documents: list[dict[str, Any]] = []
    hit_count = 0
    miss_count = 0
    for document in study_documents:
        doc_id = str(document.id)
        if doc_id in hit_scores:
            hit_count += 1
            documents.append(
                {
                    "document_id": doc_id,
                    "filename": document.filename,
                    "status": "hit",
                    "top_rerank_score": round(hit_scores[doc_id], 4),
                }
            )
        else:
            miss_count += 1
            documents.append(
                {
                    "document_id": doc_id,
                    "filename": document.filename,
                    "status": "miss",
                    "top_rerank_score": None,
                }
            )

    return {
        "documents": documents,
        "hit_count": hit_count,
        "miss_count": miss_count,
    }


def _base_payload(
    *,
    course_id: str,
    tier: int,
    answers_available: bool,
    target_type: str,
    target_id: str,
    query_text: str,
    answer_length: str,
    status: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "found": True,
        "course_id": course_id,
        "tier": tier,
        "answers_available": answers_available,
        "target_type": target_type,
        "target_id": target_id,
        "query_text": query_text,
        "answer_length": answer_length,
        "status": status,
        "answer": None,
        "sources": [],
        "coverage": coverage,
    }


def _best_prompt_for_concept(session: Session, concept_id: uuid.UUID) -> ExamQuestion | None:
    linked = list(
        session.scalars(
            select(ExamQuestion)
            .join(ExamQuestionConcept, ExamQuestionConcept.question_id == ExamQuestion.id)
            .where(ExamQuestionConcept.concept_id == concept_id)
        )
    )
    if not linked:
        return None
    return max(linked, key=lambda question: ((question.marks or 0), len(question.prompt_text)))


def answer_exam_concept_or_question(
    session: Session,
    course_id: str,
    *,
    concept_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
    structure_node_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Ground an exam concept or parsed question in study materials (never past_paper)."""
    if session.get(Course, course_id) is None:
        return {"found": False, "course_id": course_id}

    if concept_id is None and question_id is None:
        raise ValueError("Exactly one of concept_id or question_id is required")
    if concept_id is not None and question_id is not None:
        raise ValueError("Provide concept_id or question_id, not both")

    study_documents = _list_ready_study_documents(session, course_id)
    tier = _resolve_answer_tier(session, course_id, has_study_docs=bool(study_documents))
    empty_coverage = _build_coverage(study_documents, [])

    if not study_documents:
        target_type = "concept" if concept_id else "question"
        target_id = str(concept_id or question_id)
        return _base_payload(
            course_id=course_id,
            tier=1,
            answers_available=False,
            target_type=target_type,
            target_id=target_id,
            query_text="",
            answer_length="short",
            status="no_study_docs",
            coverage=empty_coverage,
        )

    budget_tier, answer_length = "budget", "short"
    if concept_id is not None:
        concept = session.get(ExamConcept, concept_id)
        if concept is None or concept.course_id != course_id:
            return {"found": False, "course_id": course_id}
        linked_question = _best_prompt_for_concept(session, concept.id)
        if linked_question is not None:
            query_text = linked_question.prompt_text.strip()
            if linked_question.marks is not None:
                query_text = f"{query_text}\n\n(Exam question — {linked_question.marks} marks.)"
            budget_tier, answer_length = marks_to_budget(linked_question.marks)
        else:
            query_text = f'Explain "{concept.label}" for exam preparation based on course materials.'
        target_type = "concept"
        target_id = str(concept.id)
    else:
        assert question_id is not None
        question = session.get(ExamQuestion, question_id)
        if question is None or question.course_id != course_id:
            return {"found": False, "course_id": course_id}
        query_text = question.prompt_text.strip()
        if question.marks is not None:
            query_text = f"{query_text}\n\n(Exam question — {question.marks} marks.)"
        budget_tier, answer_length = marks_to_budget(question.marks)
        target_type = "question"
        target_id = str(question.id)

    source_ids: list[uuid.UUID] | None = None
    if structure_node_id is not None:
        scoped_ids = _resolve_structure_scope_document_ids(session, course_id, structure_node_id)
        if scoped_ids:
            source_ids = scoped_ids

    retrieval = run_study_question(
        session,
        course_id,
        query_text,
        preset="study",
        source_ids=source_ids,
    )
    coverage = _build_coverage(study_documents, retrieval.chunks)

    if retrieval.status != "ok" or not retrieval.chunks:
        payload = _base_payload(
            course_id=course_id,
            tier=tier,
            answers_available=True,
            target_type=target_type,
            target_id=target_id,
            query_text=query_text,
            answer_length=answer_length,
            status="not_in_materials",
            coverage=coverage,
        )
        payload["refusal_reason"] = retrieval.refusal_reason
        payload["top_rerank_score"] = retrieval.top_rerank_score
        payload["sources"] = chunks_to_sources(retrieval.chunks)
        return payload

    answer = generate_study_answer(
        query_text,
        retrieval.chunks,
        preset="study",
        llm_budget_tier=budget_tier,
    )
    payload = _base_payload(
        course_id=course_id,
        tier=tier,
        answers_available=True,
        target_type=target_type,
        target_id=target_id,
        query_text=query_text,
        answer_length=answer_length,
        status="ok",
        coverage=coverage,
    )
    payload["answer"] = answer
    payload["sources"] = chunks_to_sources(retrieval.chunks)
    payload["top_rerank_score"] = retrieval.top_rerank_score
    return payload
