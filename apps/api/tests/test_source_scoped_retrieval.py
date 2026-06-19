"""Tests for source_ids validation and scoped retrieval filter wiring."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from tests.conftest import add_test_course

from app.models import Course, Document
from app.services.course_documents import validate_source_ids
from app.services.course_structure import assign_subtopic_documents, confirm_course_structure
from app.services.rag.retrieve import fetch_exam_candidates, fetch_hybrid_candidates


def _seed_course(db_session) -> tuple[uuid.UUID, uuid.UUID]:
    add_test_course(db_session, "PPL", "Programming Languages")
    notes_id = uuid.uuid4()
    paper_id = uuid.uuid4()
    db_session.add_all(
        [
            Document(
                id=notes_id,
                course_id="PPL",
                filename="PPL notes.pdf",
                doc_kind="notes",
                status="ready",
                page_count=94,
            ),
            Document(
                id=paper_id,
                course_id="PPL",
                filename="PPL previous papers.pdf",
                doc_kind="past_paper",
                status="ready",
                page_count=30,
            ),
            Document(
                id=uuid.uuid4(),
                course_id="PPL",
                filename="failed.pdf",
                doc_kind="notes",
                status="failed",
            ),
        ]
    )
    db_session.commit()
    return notes_id, paper_id


def test_validate_source_ids_rejects_empty_list(db_session) -> None:
    _seed_course(db_session)
    with pytest.raises(ValueError, match="must not be empty"):
        validate_source_ids(
            db_session,
            course_id="PPL",
            source_ids=[],
            preset="study",
        )


def test_validate_source_ids_rejects_invalid_uuid(db_session) -> None:
    _seed_course(db_session)
    with pytest.raises(ValueError, match="Invalid source_ids UUID"):
        validate_source_ids(
            db_session,
            course_id="PPL",
            source_ids=["not-a-uuid"],
            preset="study",
        )


def test_validate_source_ids_rejects_wrong_course(db_session) -> None:
    notes_id, _ = _seed_course(db_session)
    add_test_course(db_session, "CHEM", "Chemistry")
    db_session.commit()

    with pytest.raises(ValueError, match="Document not found for course"):
        validate_source_ids(
            db_session,
            course_id="CHEM",
            source_ids=[str(notes_id)],
            preset="study",
        )


def test_validate_source_ids_rejects_failed_status(db_session) -> None:
    add_test_course(db_session, "PPL", "Programming Languages")
    failed_id = uuid.uuid4()
    db_session.add(
        Document(
            id=failed_id,
            course_id="PPL",
            filename="failed.pdf",
            doc_kind="notes",
            status="failed",
        )
    )
    db_session.commit()

    with pytest.raises(ValueError, match="status not usable"):
        validate_source_ids(
            db_session,
            course_id="PPL",
            source_ids=[str(failed_id)],
            preset="study",
        )


def test_validate_source_ids_rejects_past_paper_for_study_preset(db_session) -> None:
    _, paper_id = _seed_course(db_session)
    with pytest.raises(ValueError, match="doc_kind not allowed for preset study"):
        validate_source_ids(
            db_session,
            course_id="PPL",
            source_ids=[str(paper_id)],
            preset="study",
        )


def test_validate_source_ids_rejects_notes_for_exam_preset(db_session) -> None:
    notes_id, _ = _seed_course(db_session)
    with pytest.raises(ValueError, match="doc_kind not allowed for preset exam"):
        validate_source_ids(
            db_session,
            course_id="PPL",
            source_ids=[str(notes_id)],
            preset="exam",
        )


def test_validate_source_ids_accepts_study_doc(db_session) -> None:
    notes_id, _ = _seed_course(db_session)
    parsed = validate_source_ids(
        db_session,
        course_id="PPL",
        source_ids=[str(notes_id)],
        preset="study",
    )
    assert parsed == [notes_id]


def test_validate_source_ids_accepts_exam_doc(db_session) -> None:
    _, paper_id = _seed_course(db_session)
    parsed = validate_source_ids(
        db_session,
        course_id="PPL",
        source_ids=[str(paper_id)],
        preset="exam",
    )
    assert parsed == [paper_id]


@patch("app.services.rag.retrieve._metadata_toc_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_focus_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_search", return_value=[])
@patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384])
@patch("app.services.rag.retrieve._vector_search")
def test_fetch_hybrid_candidates_passes_document_ids(
    mock_vector,
    _mock_embed,
    _mock_bm25,
    _mock_focus,
    _mock_meta,
) -> None:
    mock_vector.return_value = []
    doc_id = uuid.uuid4()

    fetch_hybrid_candidates(
        None,  # type: ignore[arg-type]
        course_id="PPL",
        question="lexemes",
        document_ids=[doc_id],
    )

    assert mock_vector.call_args.kwargs["document_ids"] == [doc_id]


@patch("app.services.rag.retrieve._count_exam_questions", return_value=0)
@patch("app.services.rag.retrieve._metadata_toc_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_focus_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_search", return_value=[])
@patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384])
@patch("app.services.rag.retrieve._vector_search")
def test_fetch_exam_candidates_passes_document_ids(
    mock_vector,
    _mock_embed,
    _mock_bm25,
    _mock_focus,
    _mock_meta,
    _mock_count,
) -> None:
    mock_vector.return_value = []
    doc_id = uuid.uuid4()

    fetch_exam_candidates(
        None,  # type: ignore[arg-type]
        course_id="PPL",
        question="lexemes",
        document_ids=[doc_id],
    )

    assert mock_vector.call_args.kwargs["document_ids"] == [doc_id]


@patch("app.services.rag.pipeline.fetch_hybrid_candidates")
def test_run_study_question_passes_source_ids(mock_fetch, db_session) -> None:
    from app.services.rag.pipeline import run_study_question

    mock_fetch.return_value = []
    doc_id = uuid.uuid4()

    run_study_question(
        db_session,
        course_id="PPL",
        question="What is a lexeme?",
        preset="study",
        source_ids=[doc_id],
    )

    assert mock_fetch.call_args.kwargs["document_ids"] == [doc_id]


@patch("app.services.rag.retrieve._metadata_toc_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_focus_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_search", return_value=[])
@patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384])
@patch("app.services.rag.retrieve._vector_search")
def test_fetch_hybrid_candidates_passes_structure_expanded_document_ids(
    mock_vector,
    _mock_embed,
    _mock_bm25,
    _mock_focus,
    _mock_meta,
    db_session,
) -> None:
    from app.models import DocumentUnitLink
    from app.services.course_structure import validate_structure_scope_ids

    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()
    confirmed = confirm_course_structure(
        db_session,
        "CHEM",
        [{"title": "Unit 1", "subtopics": ["Heat"]}],
    )
    assert confirmed is not None
    unit_id = uuid.UUID(confirmed["units"][0]["id"])
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="CHEM",
            filename="notes.pdf",
            doc_kind="notes",
            status="ready",
        )
    )
    db_session.add(DocumentUnitLink(document_id=doc_id, unit_id=unit_id))
    db_session.commit()

    expanded = validate_structure_scope_ids(
        db_session,
        course_id="CHEM",
        unit_ids=[str(unit_id)],
        part_ids=None,
        subtopic_ids=None,
        preset="study",
    )

    mock_vector.return_value = []
    fetch_hybrid_candidates(
        db_session,
        course_id="CHEM",
        question="heat",
        document_ids=expanded,
    )

    assert mock_vector.call_args.kwargs["document_ids"] == [doc_id]


@patch("app.services.rag.pipeline.fetch_hybrid_candidates")
def test_run_study_question_passes_structure_scope_as_document_ids(
    mock_fetch,
    db_session,
) -> None:
    from app.services.course_structure import confirm_course_structure
    from app.services.rag.pipeline import run_study_question

    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()
    confirmed = confirm_course_structure(
        db_session,
        "CHEM",
        [{"title": "Unit 1", "subtopics": ["Heat"]}],
    )
    assert confirmed is not None
    unit_id = uuid.UUID(confirmed["units"][0]["id"])
    subtopic_id = uuid.UUID(confirmed["units"][0]["subtopics"][0]["id"])
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="CHEM",
            filename="heat.pdf",
            doc_kind="notes",
            status="ready",
        )
    )
    db_session.commit()
    assign_subtopic_documents(db_session, "CHEM", subtopic_id, [doc_id])

    from app.services.course_structure import validate_structure_scope_ids

    expanded = validate_structure_scope_ids(
        db_session,
        course_id="CHEM",
        unit_ids=None,
        part_ids=None,
        subtopic_ids=[str(subtopic_id)],
        preset="study",
    )

    mock_fetch.return_value = []
    run_study_question(
        db_session,
        course_id="CHEM",
        question="What is heat?",
        preset="study",
        source_ids=expanded,
    )

    assert mock_fetch.call_args.kwargs["document_ids"] == expanded
    assert doc_id in expanded
