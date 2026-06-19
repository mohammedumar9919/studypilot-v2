"""Tests for topic_ids validation, scoped retrieval, structure-mode, and bulk topics."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest

from tests.conftest import add_test_course
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import Course, Document, StudyTopic
from app.services.study_topics import (
    bulk_create_study_topics,
    update_structure_mode,
    validate_topic_ids,
)

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def _seed_organized_course(db_session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    topic_a = uuid.uuid4()
    topic_b = uuid.uuid4()
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()
    db_session.add_all(
        [
            StudyTopic(id=topic_a, course_id="CHEM", title="Unit 1", sort_order=0),
            StudyTopic(id=topic_b, course_id="CHEM", title="Unit 2", sort_order=1),
            Document(
                id=doc_a,
                course_id="CHEM",
                filename="unit1.pdf",
                doc_kind="notes",
                status="ready",
                topic_id=topic_a,
            ),
            Document(
                id=doc_b,
                course_id="CHEM",
                filename="unit2.pdf",
                doc_kind="notes",
                status="ready",
                topic_id=topic_b,
            ),
        ]
    )
    db_session.commit()
    return topic_a, topic_b, doc_a


def test_validate_topic_ids_rejects_empty_list(db_session) -> None:
    _seed_organized_course(db_session)
    with pytest.raises(ValueError, match="must not be empty"):
        validate_topic_ids(db_session, course_id="CHEM", topic_ids=[], preset="study")


def test_validate_topic_ids_rejects_invalid_uuid(db_session) -> None:
    _seed_organized_course(db_session)
    with pytest.raises(ValueError, match="Invalid topic_ids UUID"):
        validate_topic_ids(db_session, course_id="CHEM", topic_ids=["bad"], preset="study")


def test_validate_topic_ids_rejects_exam_preset(db_session) -> None:
    topic_a, _, _ = _seed_organized_course(db_session)
    with pytest.raises(ValueError, match="not allowed for preset exam"):
        validate_topic_ids(
            db_session,
            course_id="CHEM",
            topic_ids=[str(topic_a)],
            preset="exam",
        )


def test_validate_topic_ids_rejects_wrong_course(db_session) -> None:
    topic_a, _, _ = _seed_organized_course(db_session)
    add_test_course(db_session, "OTHER", "Other", structure_mode="corpus")
    db_session.commit()
    with pytest.raises(ValueError, match="Study topic not found for course"):
        validate_topic_ids(
            db_session,
            course_id="OTHER",
            topic_ids=[str(topic_a)],
            preset="study",
        )


@patch("app.services.rag.retrieve._metadata_toc_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_focus_search", return_value=[])
@patch("app.services.rag.retrieve._bm25_search", return_value=[])
@patch("app.services.rag.retrieve.embed_texts", return_value=[[0.1] * 384])
@patch("app.services.rag.retrieve._vector_search")
def test_fetch_hybrid_candidates_passes_topic_ids(
    mock_vector,
    _mock_embed,
    _mock_bm25,
    _mock_focus,
    _mock_meta,
) -> None:
    from app.services.rag.retrieve import fetch_hybrid_candidates

    mock_vector.return_value = []
    topic_id = uuid.uuid4()

    fetch_hybrid_candidates(
        None,  # type: ignore[arg-type]
        course_id="CHEM",
        question="thermodynamics",
        topic_ids=[topic_id],
    )

    assert mock_vector.call_args.kwargs["topic_ids"] == [topic_id]


@patch("app.services.rag.pipeline.fetch_hybrid_candidates")
def test_run_study_question_passes_topic_ids(mock_fetch, db_session) -> None:
    from app.services.rag.pipeline import run_study_question

    mock_fetch.return_value = []
    topic_id = uuid.uuid4()

    run_study_question(
        db_session,
        course_id="CHEM",
        question="What is entropy?",
        preset="study",
        topic_ids=[topic_id],
    )

    assert mock_fetch.call_args.kwargs["topic_ids"] == [topic_id]


def test_update_structure_mode_promotes_to_organized(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()

    course = update_structure_mode(db_session, "CHEM", "organized")
    assert course.structure_mode == "organized"


def test_update_structure_mode_blocks_ppl_demotion(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL", structure_mode="mapped")
    db_session.commit()

    with pytest.raises(ValueError, match="Cannot demote mapped fixture course"):
        update_structure_mode(db_session, "PPL", "corpus")


def test_bulk_create_promotes_corpus_to_organized(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()

    topics = bulk_create_study_topics(db_session, "CHEM", titles=["Unit 1", "Unit 2"])
    course = db_session.get(Course, "CHEM")
    assert course is not None
    assert course.structure_mode == "organized"
    assert len(topics) == 2
    assert topics[0].sort_order == 0
    assert topics[1].sort_order == 1


def test_api_patch_structure_mode(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.patch(
            "/api/v1/courses/CHEM/structure-mode",
            json={"structure_mode": "organized"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["structure_mode"] == "organized"
        assert body["mode"] == "corpus"
    finally:
        _clear_db_override()


def test_api_bulk_study_topics(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post(
            "/api/v1/courses/CHEM/study-topics/bulk",
            json={"titles": ["Unit 1", "Unit 2"]},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["structure_mode"] == "organized"
        assert len(body["topics"]) == 2
    finally:
        _clear_db_override()


@patch("app.main.run_study_query")
def test_query_rejects_topic_ids_with_source_ids(mock_run, db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    topic_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    db_session.add(
        StudyTopic(id=topic_id, course_id="CHEM", title="Unit 1", sort_order=0)
    )
    db_session.add(
        Document(
            id=doc_id,
            course_id="CHEM",
            filename="notes.pdf",
            doc_kind="notes",
            status="ready",
        )
    )
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post(
            "/api/v1/query",
            json={
                "course_id": "CHEM",
                "question": "Explain entropy",
                "preset": "study",
                "source_ids": [str(doc_id)],
                "topic_ids": [str(topic_id)],
            },
        )
        assert response.status_code == 400
        assert "Only one of source_ids, topic_ids, or structure scope" in response.json()["detail"]
        mock_run.assert_not_called()
    finally:
        _clear_db_override()


@patch("app.main.run_study_query")
def test_query_passes_validated_topic_ids(mock_run, db_session) -> None:
    topic_a, _, _ = _seed_organized_course(db_session)

    _override_db(db_session)
    mock_run.return_value = __import__(
        "app.services.rag.pipeline", fromlist=["StudyQueryResult"]
    ).StudyQueryResult(
        status="not_in_materials",
        answer=None,
        sources=[],
        rerank_scores=[],
    )
    try:
        response = client.post(
            "/api/v1/query",
            json={
                "course_id": "CHEM",
                "question": "Explain entropy",
                "preset": "study",
                "topic_ids": [str(topic_a)],
            },
        )
        assert response.status_code == 200
        assert mock_run.call_args.kwargs["topic_ids"] == [topic_a]
        assert mock_run.call_args.kwargs["source_ids"] is None
    finally:
        _clear_db_override()
