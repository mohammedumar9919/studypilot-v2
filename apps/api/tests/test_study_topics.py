"""Tests for study_topics CRUD, structure_mode migration, and layout mode."""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "004_study_topics.py"
_spec = importlib.util.spec_from_file_location("migration_004_study_topics", _migration_path)
assert _spec and _spec.loader
migration_004 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_004)
from app.database import get_session
from app.main import app
from app.models import Course, Document
from app.services.study_layout import get_study_layout, resolve_structure_mode, resolve_study_layout_mode
from app.services.study_topics import (
    assign_document_topic,
    create_study_topic,
    delete_study_topic,
    list_study_topics,
    update_study_topic,
)
from tests.conftest import add_test_course

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def test_migration_backfill_structure_mode(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL", structure_mode="corpus")
    add_test_course(db_session, "chemistry", "Chemistry", structure_mode="corpus")
    add_test_course(
        db_session,
        "HIGHQ",
        "High quality",
        structure_mode="corpus",
        outline_data={"outline_quality": "high"},
    )
    add_test_course(db_session, "PLAIN", "Plain", structure_mode="corpus")
    db_session.commit()

    migration_004.apply_structure_mode_backfill(db_session.connection())

    assert db_session.get(Course, "PPL").structure_mode == "mapped"
    assert db_session.get(Course, "chemistry").structure_mode == "mapped"
    assert db_session.get(Course, "HIGHQ").structure_mode == "mapped"
    assert db_session.get(Course, "PLAIN").structure_mode == "corpus"


def test_resolve_structure_mode_uses_persisted_value(db_session) -> None:
    course = add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    db_session.commit()

    assert resolve_structure_mode("CHEM", course=course) == "organized"


def test_organized_structure_mode_maps_to_corpus_sidebar(db_session) -> None:
    course = add_test_course(db_session, "ORG", "Organized", structure_mode="organized")
    db_session.commit()

    assert resolve_study_layout_mode("ORG", course=course) == "corpus"
    layout = get_study_layout(db_session, "ORG")
    assert layout is not None
    assert layout["structure_mode"] == "organized"
    assert layout["mode"] == "corpus"


def test_study_topic_crud(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    db_session.commit()

    topic = create_study_topic(db_session, "CHEM", title="Thermodynamics", sort_order=1)
    assert topic.title == "Thermodynamics"

    topics = list_study_topics(db_session, "CHEM")
    assert topics is not None
    assert len(topics) == 1

    updated = update_study_topic(
        db_session,
        "CHEM",
        topic.id,
        title="Thermo updated",
        sort_order=2,
    )
    assert updated.title == "Thermo updated"
    assert updated.sort_order == 2

    delete_study_topic(db_session, "CHEM", topic.id)
    assert list_study_topics(db_session, "CHEM") == []


def test_assign_document_topic(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
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
    db_session.commit()

    topic = create_study_topic(db_session, "CHEM", title="Unit 1")
    document = assign_document_topic(db_session, doc_id, topic_id=topic.id)
    assert document.topic_id == topic.id

    cleared = assign_document_topic(db_session, doc_id, topic_id=None)
    assert cleared.topic_id is None


def test_assign_document_topic_rejects_cross_course(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    add_test_course(db_session, "PPL", "PPL", structure_mode="mapped")
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
    db_session.commit()

    ppl_topic = create_study_topic(db_session, "PPL", title="Unit 1")
    with pytest.raises(ValueError, match="not found for document course"):
        assign_document_topic(db_session, doc_id, topic_id=ppl_topic.id)


def test_api_study_topics_crud(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
    db_session.commit()

    _override_db(db_session)
    try:
        create_resp = client.post(
            "/api/v1/courses/CHEM/study-topics",
            json={"title": "Organic", "sort_order": 1},
        )
        assert create_resp.status_code == 201
        topic_id = create_resp.json()["id"]

        list_resp = client.get("/api/v1/courses/CHEM/study-topics")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["topics"]) == 1

        patch_resp = client.patch(
            f"/api/v1/courses/CHEM/study-topics/{topic_id}",
            json={"title": "Organic Chemistry"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "Organic Chemistry"

        delete_resp = client.delete(f"/api/v1/courses/CHEM/study-topics/{topic_id}")
        assert delete_resp.status_code == 204
    finally:
        _clear_db_override()


def test_api_patch_document_topic(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
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
    db_session.commit()
    topic = create_study_topic(db_session, "CHEM", title="Unit 1")

    _override_db(db_session)
    try:
        response = client.patch(
            f"/api/v1/documents/{doc_id}",
            json={"topic_id": str(topic.id)},
        )
        assert response.status_code == 200
        assert response.json()["topic_id"] == str(topic.id)

        clear_resp = client.patch(f"/api/v1/documents/{doc_id}", json={"topic_id": None})
        assert clear_resp.status_code == 200
        assert clear_resp.json()["topic_id"] is None
    finally:
        _clear_db_override()


def test_ppl_mapped_after_structure_mode_set(db_session) -> None:
    add_test_course(db_session, "PPL", "Programming Languages", structure_mode="mapped")
    db_session.commit()

    layout = get_study_layout(db_session, "PPL")
    assert layout is not None
    assert layout["mode"] == "mapped"
    assert layout["structure_mode"] == "mapped"

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/PPL/study-layout")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "mapped"
        assert body["structure_mode"] == "mapped"
    finally:
        _clear_db_override()


def test_delete_topic_clears_document_assignment(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="organized")
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
    db_session.commit()
    topic = create_study_topic(db_session, "CHEM", title="Unit 1")
    assign_document_topic(db_session, doc_id, topic_id=topic.id)

    delete_study_topic(db_session, "CHEM", topic.id)
    document = db_session.get(Document, doc_id)
    db_session.refresh(document)
    assert document is not None
    assert document.topic_id is None
