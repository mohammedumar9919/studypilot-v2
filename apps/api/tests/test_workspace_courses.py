"""Tests for SP-012c workspace course list/create APIs and upload auto-create."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import Course, Workspace
from app.services.workspaces import SYSTEM_DEMO_WORKSPACE_ID, SYSTEM_DEMO_WORKSPACE_SLUG
from tests.conftest import add_test_course

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def test_get_workspace_me_bypass(db_session: Session) -> None:
    _override_db(db_session)
    try:
        response = client.get("/api/v1/workspaces/me")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(SYSTEM_DEMO_WORKSPACE_ID)
        assert body["slug"] == SYSTEM_DEMO_WORKSPACE_SLUG
        assert body["name"]
    finally:
        _clear_db_override()


def test_list_courses_in_demo_workspace(db_session: Session) -> None:
    add_test_course(db_session, "PPL", "Programming Languages", structure_mode="mapped")
    add_test_course(db_session, "CHEM101", "Chemistry 101")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/workspaces/me/courses")
        assert response.status_code == 200
        courses = response.json()
        assert [course["id"] for course in courses] == ["CHEM101", "PPL"]
        assert courses[0]["structure_mode"] == "corpus"
        assert courses[1]["structure_mode"] == "mapped"
        assert courses[0]["created_at"] is not None
    finally:
        _clear_db_override()


def test_create_course_in_workspace(db_session: Session) -> None:
    _override_db(db_session)
    try:
        create = client.post(
            "/api/v1/workspaces/me/courses",
            json={"id": "BIO101", "name": "Intro Biology"},
        )
        assert create.status_code == 201
        body = create.json()
        assert body["id"] == "BIO101"
        assert body["name"] == "Intro Biology"
        assert body["structure_mode"] == "corpus"
        assert body["created_at"] is not None

        listing = client.get("/api/v1/workspaces/me/courses")
        assert listing.status_code == 200
        assert any(course["id"] == "BIO101" for course in listing.json())
    finally:
        _clear_db_override()


def test_duplicate_course_409(db_session: Session) -> None:
    add_test_course(db_session, "PHYS101", "Physics")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post(
            "/api/v1/workspaces/me/courses",
            json={"id": "PHYS101", "name": "Physics Again"},
        )
        assert response.status_code == 409
        assert "already exists in workspace" in response.json()["detail"]
    finally:
        _clear_db_override()


def test_invalid_course_id_422(db_session: Session) -> None:
    _override_db(db_session)
    try:
        response = client.post(
            "/api/v1/workspaces/me/courses",
            json={"id": "bad-id", "name": "Invalid"},
        )
        assert response.status_code == 422
        assert "Course id must match" in response.json()["detail"]
    finally:
        _clear_db_override()


def test_course_in_other_workspace_not_listed(db_session: Session) -> None:
    other_workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(
            id=other_workspace_id,
            name="Private",
            slug="private-workspace-courses",
        )
    )
    db_session.add(
        Course(
            id="PRIVATE101",
            name="Private Course",
            workspace_id=other_workspace_id,
        )
    )
    add_test_course(db_session, "PPL", "Programming Languages")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/workspaces/me/courses")
        assert response.status_code == 200
        ids = [course["id"] for course in response.json()]
        assert ids == ["PPL"]
        assert "PRIVATE101" not in ids
    finally:
        _clear_db_override()


@patch("app.main.upload_and_ingest_document")
def test_upload_auto_creates_course_in_workspace(mock_upload, db_session: Session) -> None:
    mock_upload.return_value = {
        "document_id": str(uuid.uuid4()),
        "course_id": "NEW101",
        "filename": "notes.pdf",
        "doc_kind": "notes",
        "status": "ready",
        "page_count": 1,
        "upload_intent": "quick",
        "extraction_quality": {"nonempty_pages": 1, "upload_intent": "quick"},
    }

    _override_db(db_session)
    try:
        response = client.post(
            "/api/v1/courses/NEW101/documents",
            files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
            data={"doc_kind": "notes"},
        )
        assert response.status_code == 201
        assert response.json()["course_id"] == "NEW101"

        course = db_session.get(Course, "NEW101")
        assert course is not None
        assert course.workspace_id == SYSTEM_DEMO_WORKSPACE_ID

        listing = client.get("/api/v1/workspaces/me/courses")
        assert any(item["id"] == "NEW101" for item in listing.json())
        mock_upload.assert_called_once()
    finally:
        _clear_db_override()
