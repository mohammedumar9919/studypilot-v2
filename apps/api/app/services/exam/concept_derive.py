"""Ingest-time course-level exam concept derivation (idempotent delete+rebuild)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ExamConcept, ExamConceptAlias, ExamQuestion, ExamQuestionConcept
from app.services.course_structure import get_course_structure
from app.services.exam.concept_canonicalize import ConceptCluster, canonicalize_phrases
from app.services.exam.concept_extract import ExtractedPhrase, extract_keyphrases, normalize_phrase

UNCLASSIFIED_LABEL = "Unclassified"
MIN_ASSIGNMENT_CONFIDENCE = 0.12


@dataclass(frozen=True, slots=True)
class DeriveStats:
    course_id: str
    question_count: int
    concept_count: int
    classified_concept_count: int
    alias_count: int
    linked_questions: int
    unclassified_only_questions: int
    unclassified_pct: float


def _delete_course_concepts(session: Session, course_id: str) -> None:
    session.execute(delete(ExamConcept).where(ExamConcept.course_id == course_id))


def _phrase_matches_cluster(phrase: ExtractedPhrase, cluster: ConceptCluster) -> float:
    if phrase.normalized in cluster.terms:
        return phrase.score
    return 0.0


def derive_exam_concepts_for_course(session: Session, course_id: str) -> DeriveStats:
    """Delete and rebuild all exam concepts for a course from parsed questions."""
    questions = list(
        session.scalars(
            select(ExamQuestion)
            .where(ExamQuestion.course_id == course_id)
            .order_by(ExamQuestion.page, ExamQuestion.question_number)
        )
    )

    _delete_course_concepts(session, course_id)
    session.flush()

    if not questions:
        session.flush()
        return DeriveStats(
            course_id=course_id,
            question_count=0,
            concept_count=0,
            classified_concept_count=0,
            alias_count=0,
            linked_questions=0,
            unclassified_only_questions=0,
            unclassified_pct=0.0,
        )

    per_question_phrases: list[list[ExtractedPhrase]] = [
        extract_keyphrases(question.prompt_text) for question in questions
    ]
    all_phrases = [phrase for phrases in per_question_phrases for phrase in phrases]
    subtopic_titles: list[str] = []
    structure = get_course_structure(session, course_id)
    if structure:
        for unit in structure.get("units", []):
            subtopic_titles.append(str(unit.get("title", "")))
            for subtopic in unit.get("subtopics") or []:
                subtopic_titles.append(str(subtopic.get("title", "")))
            for part in unit.get("parts") or []:
                subtopic_titles.append(str(part.get("title", "")))
                for subtopic in part.get("subtopics") or []:
                    subtopic_titles.append(str(subtopic.get("title", "")))
    subtopic_titles = [title.strip() for title in subtopic_titles if title and title.strip()]
    clusters = canonicalize_phrases(
        all_phrases,
        question_count=len(questions),
        subtopic_titles=subtopic_titles or None,
    )

    unclassified = ExamConcept(
        course_id=course_id,
        label=UNCLASSIFIED_LABEL,
        canonical_terms=[],
        confidence=0.0,
        is_unclassified=True,
    )
    session.add(unclassified)
    session.flush()

    concept_rows: list[ExamConcept] = []
    alias_rows: list[ExamConceptAlias] = []
    term_to_concept: dict[str, ExamConcept] = {normalize_phrase(UNCLASSIFIED_LABEL): unclassified}

    for cluster in clusters:
        if cluster.label == UNCLASSIFIED_LABEL:
            continue
        concept = ExamConcept(
            course_id=course_id,
            label=cluster.label,
            canonical_terms=list(cluster.terms),
            confidence=cluster.confidence,
            is_unclassified=False,
        )
        session.add(concept)
        concept_rows.append(concept)
        session.flush()
        for term in cluster.terms:
            term_to_concept[term] = concept
            alias_rows.append(
                ExamConceptAlias(course_id=course_id, alias=term, concept_id=concept.id)
            )

    session.add_all(alias_rows)
    session.flush()

    linked_questions = 0
    unclassified_only = 0

    for question, phrases in zip(questions, per_question_phrases, strict=True):
        matches: dict[ExamConcept, float] = {}
        for phrase in phrases:
            for cluster in clusters:
                weight = _phrase_matches_cluster(phrase, cluster)
                if weight <= 0:
                    continue
                concept = term_to_concept.get(phrase.normalized)
                if concept is None:
                    for term in cluster.terms:
                        concept = term_to_concept.get(term)
                        if concept is not None:
                            break
                if concept is None or concept.is_unclassified:
                    continue
                matches[concept] = max(matches.get(concept, 0.0), weight)

        strong = {concept: weight for concept, weight in matches.items() if weight >= MIN_ASSIGNMENT_CONFIDENCE}

        if not strong:
            session.add(
                ExamQuestionConcept(
                    question_id=question.id,
                    concept_id=unclassified.id,
                    weight=1.0,
                )
            )
            unclassified_only += 1
            continue

        linked_questions += 1
        total = sum(strong.values())
        for concept, weight in strong.items():
            session.add(
                ExamQuestionConcept(
                    question_id=question.id,
                    concept_id=concept.id,
                    weight=weight / total,
                )
            )

    session.flush()

    classified_count = len(concept_rows)
    total_concepts = classified_count + 1
    unclassified_pct = (unclassified_only / len(questions) * 100.0) if questions else 0.0

    return DeriveStats(
        course_id=course_id,
        question_count=len(questions),
        concept_count=total_concepts,
        classified_concept_count=classified_count,
        alias_count=len(alias_rows),
        linked_questions=linked_questions,
        unclassified_only_questions=unclassified_only,
        unclassified_pct=round(unclassified_pct, 2),
    )
