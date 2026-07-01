"""Read-only Tier 1 exam concept analytics (marks-weighted, no LLM)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ExamConcept, ExamConceptAlias, ExamQuestion, ExamQuestionConcept
from app.services.exam.exam_status import compute_exam_status

LONG_QUESTION_THRESHOLD_MARKS = 8
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

SortKey = Literal["weightage_desc", "count_desc", "label_asc"]
_VALID_SORTS = frozenset({"weightage_desc", "count_desc", "label_asc"})

_YEAR_RE = re.compile(r"(20\d{2})")


def _question_marks(question: ExamQuestion) -> int:
    return question.marks if question.marks is not None else 1


def _parse_year(paper_label: str | None) -> int | None:
    if not paper_label:
        return None
    match = _YEAR_RE.search(paper_label)
    return int(match.group(1)) if match else None


def _linear_slope(year_counts: dict[int, int]) -> float | None:
    if len(year_counts) < 2:
        return None
    xs = sorted(year_counts)
    ys = [year_counts[year] for year in xs]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _empty_response(course_id: str, *, status: dict[str, Any]) -> dict[str, Any]:
    return {
        "found": True,
        "course_id": course_id,
        "tier": 1,
        "analytics_ready": False,
        "summary": {
            "question_count": status.get("parsed_questions", 0),
            "concept_count": 0,
            "classified_concept_count": 0,
            "unclassified_only_questions": 0,
            "unclassified_pct": 0.0,
            "total_marks": 0,
            "distinct_papers": 0,
            "long_question_threshold_marks": LONG_QUESTION_THRESHOLD_MARKS,
        },
        "concepts": [],
        "pagination": {"limit": DEFAULT_LIMIT, "offset": 0, "total": 0},
    }


def compute_exam_analytics(
    session: Session,
    course_id: str,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    sort: str = "weightage_desc",
    include_unclassified: bool = False,
    min_questions: int = 1,
) -> dict[str, Any]:
    """Aggregate persisted exam concept analytics for a course."""
    status = compute_exam_status(session, course_id)
    if not status.get("found"):
        return {"found": False, "course_id": course_id}

    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    min_questions = max(1, min_questions)
    if sort not in _VALID_SORTS:
        raise ValueError(f"Unsupported sort: {sort}")

    parsed_questions = int(status.get("parsed_questions") or 0)
    if parsed_questions == 0:
        payload = _empty_response(course_id, status=status)
        payload["pagination"] = {"limit": limit, "offset": offset, "total": 0}
        return payload

    concepts = list(
        session.scalars(
            select(ExamConcept)
            .where(ExamConcept.course_id == course_id)
            .options(selectinload(ExamConcept.aliases))
        )
    )
    links = list(
        session.scalars(
            select(ExamQuestionConcept)
            .join(ExamQuestion, ExamQuestion.id == ExamQuestionConcept.question_id)
            .where(ExamQuestion.course_id == course_id)
            .options(
                selectinload(ExamQuestionConcept.question),
                selectinload(ExamQuestionConcept.concept),
            )
        )
    )

    questions = list(
        session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == course_id))
    )
    question_by_id = {question.id: question for question in questions}
    total_marks = sum(_question_marks(question) for question in questions)
    distinct_papers = {
        question.paper_label
        for question in questions
        if question.paper_label
    }
    distinct_paper_count = len(distinct_papers) or 1

    classified_concepts = [concept for concept in concepts if not concept.is_unclassified]
    unclassified_concepts = [concept for concept in concepts if concept.is_unclassified]
    unclassified_ids = {concept.id for concept in unclassified_concepts}

    question_classified: dict[Any, set[Any]] = defaultdict(set)
    question_unclassified: dict[Any, bool] = defaultdict(bool)
    for link in links:
        if link.concept_id in unclassified_ids:
            question_unclassified[link.question_id] = True
        else:
            question_classified[link.question_id].add(link.concept_id)

    unclassified_only_questions = sum(
        1
        for question_id in question_by_id
        if question_unclassified[question_id] and not question_classified[question_id]
    )
    unclassified_pct = round(
        (unclassified_only_questions / parsed_questions * 100.0) if parsed_questions else 0.0,
        2,
    )

    per_concept_links: dict[Any, list[ExamQuestionConcept]] = defaultdict(list)
    for link in links:
        per_concept_links[link.concept_id].append(link)

    concept_rows: list[dict[str, Any]] = []
    for concept in concepts:
        if concept.is_unclassified and not include_unclassified:
            continue

        concept_links = per_concept_links.get(concept.id, [])
        if not concept_links:
            continue

        weighted_question_count = 0.0
        unique_question_ids: set[Any] = set()
        marks_total = 0.0
        long_count = 0
        short_count = 0
        papers: set[str] = set()
        year_counts: dict[int, int] = defaultdict(int)

        for link in concept_links:
            question = link.question or question_by_id.get(link.question_id)
            if question is None:
                continue
            weight = link.weight
            weighted_question_count += weight
            unique_question_ids.add(question.id)
            q_marks = _question_marks(question)
            marks_total += q_marks * weight
            if q_marks >= LONG_QUESTION_THRESHOLD_MARKS:
                long_count += 1
            else:
                short_count += 1
            if question.paper_label:
                papers.add(question.paper_label)
                year = _parse_year(question.paper_label)
                if year is not None:
                    year_counts[year] += 1

        unique_question_count = len(unique_question_ids)
        if unique_question_count < min_questions:
            continue

        weightage_pct = round((marks_total / total_marks * 100.0) if total_marks else 0.0, 2)
        count_pct = round(
            (unique_question_count / parsed_questions * 100.0) if parsed_questions else 0.0,
            2,
        )
        paper_reach = len(papers)
        recurrence_rate = round(paper_reach / distinct_paper_count, 4)
        avg_marks = round(marks_total / weighted_question_count, 2) if weighted_question_count else 0.0

        years = sorted(year_counts)
        last_seen_paper = str(years[-1]) if years else None

        aliases = sorted(
            {
                alias.alias
                for alias in concept.aliases
                if alias.alias != concept.label.lower()
            }
        )
        canonical_terms = list(concept.canonical_terms or [])
        for term in canonical_terms:
            if term not in aliases and term != concept.label:
                aliases.append(term)

        concept_rows.append(
            {
                "concept_id": str(concept.id),
                "label": concept.label,
                "aliases": aliases,
                "is_unclassified": concept.is_unclassified,
                "question_count": round(weighted_question_count, 4),
                "unique_question_count": unique_question_count,
                "marks_total": round(marks_total, 2),
                "weightage_pct": weightage_pct,
                "count_pct": count_pct,
                "paper_reach": paper_reach,
                "recurrence_rate": recurrence_rate,
                "avg_marks": avg_marks,
                "long_count": long_count,
                "short_count": short_count,
                "last_seen_paper": last_seen_paper,
                "trend_slope": _linear_slope(year_counts),
            }
        )

    if sort == "weightage_desc":
        concept_rows.sort(
            key=lambda row: (-row["weightage_pct"], -row["unique_question_count"], row["label"].lower())
        )
    elif sort == "count_desc":
        concept_rows.sort(
            key=lambda row: (-row["unique_question_count"], -row["weightage_pct"], row["label"].lower())
        )
    else:
        concept_rows.sort(key=lambda row: row["label"].lower())

    total = len(concept_rows)
    page = concept_rows[offset : offset + limit]
    for rank, row in enumerate(page, start=offset + 1):
        row["rank"] = rank

    return {
        "found": True,
        "course_id": course_id,
        "tier": 1,
        "analytics_ready": True,
        "summary": {
            "question_count": parsed_questions,
            "concept_count": len(concepts),
            "classified_concept_count": len(classified_concepts),
            "unclassified_only_questions": unclassified_only_questions,
            "unclassified_pct": unclassified_pct,
            "total_marks": total_marks,
            "distinct_papers": len(distinct_papers),
            "long_question_threshold_marks": LONG_QUESTION_THRESHOLD_MARKS,
        },
        "concepts": page,
        "pagination": {"limit": limit, "offset": offset, "total": total},
    }


def compute_exam_analytics_json(session: Session, course_id: str, **kwargs: Any) -> str:
    return json.dumps(compute_exam_analytics(session, course_id, **kwargs), indent=2)
