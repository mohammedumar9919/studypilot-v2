"""Tests for SP-012b Clerk JWT auth + dev bypass."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.main import app
from app.models import Course, Workspace
from app.services.rag.pipeline import StudyQueryResult
from tests.conftest import add_test_course

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


@patch("app.main.run_study_query")
def test_routes_work_without_auth_when_bypass_enabled(mock_run, db_session: Session) -> None:
    mock_run.return_value = StudyQueryResult(
        status="not_in_materials",
        answer=None,
        sources=[],
        rerank_scores=[],
    )
    add_test_course(db_session, "PPL", "Programming Languages", structure_mode="mapped")
    db_session.commit()

    _override_db(db_session)
    try:
        assert settings.auth_disabled()

        layout = client.get("/api/v1/courses/PPL/study-layout")
        assert layout.status_code == 200
        assert layout.json()["course_id"] == "PPL"

        query = client.post(
            "/api/v1/query",
            json={"course_id": "PPL", "question": "What is BNF?"},
        )
        assert query.status_code == 200
        mock_run.assert_called_once()
    finally:
        _clear_db_override()


def test_missing_token_returns_401_when_auth_enabled(db_session: Session, monkeypatch) -> None:
    add_test_course(db_session, "PPL", "Programming Languages")
    db_session.commit()

    monkeypatch.setattr(settings, "studypilot_auth_disabled", False)
    monkeypatch.setattr(settings, "environment", "development")

    _override_db(db_session)
    try:
        assert not settings.auth_disabled()
        response = client.get("/api/v1/courses/PPL/study-layout")
        assert response.status_code == 401
    finally:
        _clear_db_override()


def test_wrong_workspace_returns_404(db_session: Session) -> None:
    other_workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(
            id=other_workspace_id,
            name="Private",
            slug="private-auth-test",
        )
    )
    db_session.add(
        Course(
            id="PRIVATE",
            name="Private Course",
            workspace_id=other_workspace_id,
        )
    )
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/PRIVATE/study-layout")
        assert response.status_code == 404
        assert "Course not found" in response.json()["detail"]
    finally:
        _clear_db_override()


def test_health_stays_public(db_session: Session) -> None:
    _override_db(db_session)
    try:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        _clear_db_override()
