"""Schema tests for exam concept tables (SP-060a — Agent D).

Algorithm tests (extract, canonicalize, derive) are owned by Agent B.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Document,
    ExamConcept,
    ExamConceptAlias,
    ExamQuestion,
    ExamQuestionConcept,
)
from tests.conftest import add_test_course


def _add_past_paper_question(db_session: Session, course_id: str = "PPL") -> ExamQuestion:
    add_test_course(db_session, course_id, course_id)
    doc = Document(
        id=uuid.uuid4(),
        course_id=course_id,
        filename="pyq.pdf",
        doc_kind="past_paper",
        status="ready",
        page_count=1,
    )
    db_session.add(doc)
    question = ExamQuestion(
        document_id=doc.id,
        course_id=course_id,
        page=1,
        prompt_text="Explain polymorphism in OOP.",
        extraction_method="regex",
    )
    db_session.add(question)
    db_session.flush()
    return question


def test_schema_tables_exist(migrated_db) -> None:
    from app.config import settings
    from sqlalchemy import create_engine

    engine = create_engine(settings.test_database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "exam_concepts" in tables
    assert "exam_concept_aliases" in tables
    assert "exam_question_concepts" in tables


def test_schema_fk_exam_concepts_requires_course(db_session: Session) -> None:
    db_session.add(
        ExamConcept(
            course_id="MISSING",
            label="Pointers",
            canonical_terms=["pointer"],
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schema_fk_alias_requires_concept(db_session: Session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    db_session.commit()

    db_session.add(
        ExamConceptAlias(
            course_id="PPL",
            alias="ptr",
            concept_id=uuid.uuid4(),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schema_fk_question_concept_requires_question_and_concept(db_session: Session) -> None:
    question = _add_past_paper_question(db_session)
    concept = ExamConcept(
        course_id="PPL",
        label="OOP",
        canonical_terms=["object-oriented"],
    )
    db_session.add(concept)
    db_session.flush()

    db_session.add(
        ExamQuestionConcept(
            question_id=uuid.uuid4(),
            concept_id=concept.id,
            weight=1.0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        ExamQuestionConcept(
            question_id=question.id,
            concept_id=uuid.uuid4(),
            weight=1.0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schema_question_concept_links_relationship(db_session: Session) -> None:
    question = _add_past_paper_question(db_session)
    concept = ExamConcept(
        course_id="PPL",
        label="Polymorphism",
        canonical_terms=["polymorphism", "inheritance"],
        confidence=0.9,
    )
    db_session.add(concept)
    db_session.flush()
    db_session.add(
        ExamQuestionConcept(
            question_id=question.id,
            concept_id=concept.id,
            weight=0.75,
        )
    )
    db_session.commit()

    db_session.refresh(question)
    assert len(question.concept_links) == 1
    assert question.concept_links[0].weight == 0.75
    assert question.concept_links[0].concept.label == "Polymorphism"


def test_schema_alias_composite_pk_per_course(db_session: Session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    concept_a = ExamConcept(course_id="PPL", label="A", canonical_terms=["a"])
    concept_b = ExamConcept(course_id="PPL", label="B", canonical_terms=["b"])
    db_session.add_all([concept_a, concept_b])
    db_session.flush()

    db_session.add(ExamConceptAlias(course_id="PPL", alias="shared", concept_id=concept_a.id))
    db_session.commit()

    db_session.add(ExamConceptAlias(course_id="PPL", alias="shared", concept_id=concept_b.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schema_one_unclassified_bucket_per_course(db_session: Session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    db_session.add(
        ExamConcept(
            course_id="PPL",
            label="Unclassified",
            canonical_terms=[],
            is_unclassified=True,
        )
    )
    db_session.commit()

    db_session.add(
        ExamConcept(
            course_id="PPL",
            label="Other Unclassified",
            canonical_terms=[],
            is_unclassified=True,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schema_idempotent_course_delete_cascades(db_session: Session) -> None:
    question = _add_past_paper_question(db_session)
    concept = ExamConcept(
        course_id="PPL",
        label="Types",
        canonical_terms=["static typing"],
        is_unclassified=False,
    )
    db_session.add(concept)
    db_session.flush()
    db_session.add(ExamConceptAlias(course_id="PPL", alias="typing", concept_id=concept.id))
    db_session.add(
        ExamQuestionConcept(question_id=question.id, concept_id=concept.id, weight=1.0)
    )
    db_session.commit()

    concept_id = concept.id
    db_session.execute(text("DELETE FROM exam_concepts WHERE course_id = 'PPL'"))
    db_session.commit()

    assert db_session.get(ExamConcept, concept_id) is None
    assert db_session.query(ExamConceptAlias).filter_by(course_id="PPL").count() == 0
    assert db_session.query(ExamQuestionConcept).filter_by(concept_id=concept_id).count() == 0
    assert db_session.get(ExamQuestion, question.id) is not None

from app.services.exam.concept_canonicalize import (
    MIN_QUESTIONS_FOR_CLUSTERING,
    canonicalize_phrases,
)
from app.services.exam.concept_derive import derive_exam_concepts_for_course
from app.services.exam.concept_extract import extract_acronym_links, extract_keyphrases

SEED_PATH = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl" / "ppl_concept_seed.yaml"


def _load_concept_seed() -> dict:
    return yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))


def test_extract_keyphrases_yake_style() -> None:
    phrases = extract_keyphrases(
        "Define Operator precedence and operator associativity for boolean expressions."
    )
    normalized = [item.normalized for item in phrases]
    assert any("operator precedence" in term for term in normalized)
    assert phrases[0].score >= phrases[-1].score


def test_extract_acronym_parenthetical_and_allcaps() -> None:
    links = extract_acronym_links("Abstract Data Types (ADT) are used in OOP designs.")
    assert links.get("adt") == "abstract data types"
    assert "oop" in links

    phrases = extract_keyphrases("Explain Abstract Data Types (ADT) in OOP.")
    normalized = {item.normalized for item in phrases}
    assert "abstract data types" in normalized or "adt" in normalized


def test_canonicalize_skips_merge_below_five_questions() -> None:
    phrases_a = extract_keyphrases("Define polymorphism in OOP.")
    phrases_b = extract_keyphrases("Explain polymorphic dispatch.")
    clusters = canonicalize_phrases(phrases_a + phrases_b, question_count=4)
    assert len(clusters) == len(phrases_a) + len(phrases_b)


def test_canonicalize_greedy_merge_at_threshold() -> None:
    left = extract_keyphrases("Define object oriented programming features.")
    right = extract_keyphrases("Explain object oriented programming principles.")
    clusters = canonicalize_phrases(left + right, question_count=MIN_QUESTIONS_FOR_CLUSTERING)
    labels = [cluster.label.lower() for cluster in clusters]
    assert any("object oriented programming" in label for label in labels)
    assert len(clusters) < len(left) + len(right)


def test_derive_unclassified_only_for_low_signal_prompt(db_session: Session) -> None:
    seed = _load_concept_seed()
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        id=uuid.uuid4(),
        course_id="PPL",
        filename="low.pdf",
        doc_kind="past_paper",
        status="ready",
        page_count=1,
    )
    db_session.add(doc)
    db_session.add(
        ExamQuestion(
            document_id=doc.id,
            course_id="PPL",
            page=1,
            prompt_text=seed["unclassified_case"]["prompt"],
            extraction_method="regex",
        )
    )
    db_session.commit()

    stats = derive_exam_concepts_for_course(db_session, "PPL")
    db_session.commit()

    assert stats.unclassified_only_questions == 1
    unclassified = (
        db_session.query(ExamConcept)
        .filter_by(course_id="PPL", is_unclassified=True)
        .one()
    )
    links = db_session.query(ExamQuestionConcept).filter_by(concept_id=unclassified.id).all()
    assert len(links) == 1


def test_derive_multi_label_question(db_session: Session) -> None:
    seed = _load_concept_seed()
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        id=uuid.uuid4(),
        course_id="PPL",
        filename="multi.pdf",
        doc_kind="past_paper",
        status="ready",
        page_count=1,
    )
    db_session.add(doc)
    question = ExamQuestion(
        document_id=doc.id,
        course_id="PPL",
        page=1,
        prompt_text=seed["multi_label_case"]["prompt"],
        extraction_method="regex",
    )
    db_session.add(question)
    db_session.commit()

    derive_exam_concepts_for_course(db_session, "PPL")
    db_session.commit()

    db_session.refresh(question)
    classified_links = [
        link for link in question.concept_links if not link.concept.is_unclassified
    ]
    assert len(classified_links) >= seed["multi_label_case"]["min_concepts"]


def test_derive_idempotent_course_rebuild(db_session: Session) -> None:
    seed = _load_concept_seed()
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        id=uuid.uuid4(),
        course_id="PPL",
        filename="idem.pdf",
        doc_kind="past_paper",
        status="ready",
        page_count=1,
    )
    db_session.add(doc)
    for idx, prompt in enumerate(seed["idempotent_questions"], start=1):
        db_session.add(
            ExamQuestion(
                document_id=doc.id,
                course_id="PPL",
                page=idx,
                prompt_text=prompt,
                extraction_method="regex",
            )
        )
    db_session.commit()

    first = derive_exam_concepts_for_course(db_session, "PPL")
    db_session.commit()
    second = derive_exam_concepts_for_course(db_session, "PPL")
    db_session.commit()

    assert first.concept_count == second.concept_count
    assert first.alias_count == second.alias_count
    assert first.linked_questions == second.linked_questions
    assert first.unclassified_only_questions == second.unclassified_only_questions


def test_derive_fixture_prompt_labels(db_session: Session) -> None:
    seed = _load_concept_seed()
    add_test_course(db_session, "PPL", "PPL")
    doc = Document(
        id=uuid.uuid4(),
        course_id="PPL",
        filename="fixture.pdf",
        doc_kind="past_paper",
        status="ready",
        page_count=3,
    )
    db_session.add(doc)
    for idx, case in enumerate(seed["fixture_prompts"], start=1):
        db_session.add(
            ExamQuestion(
                document_id=doc.id,
                course_id="PPL",
                page=idx,
                prompt_text=case["prompt"],
                extraction_method="regex",
            )
        )
    db_session.commit()

    derive_exam_concepts_for_course(db_session, "PPL")
    db_session.commit()

    labels = {
        row.label.lower()
        for row in db_session.query(ExamConcept).filter_by(course_id="PPL", is_unclassified=False)
    }
    for case in seed["fixture_prompts"]:
        for expected in case["expect_labels_contain"]:
            assert any(expected in label for label in labels)
