"""Tests for GET /api/v1/documents/{document_id}/ingest-status (SP-013b)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Document
from app.services.ingest_queue import enqueue_ingest_job, get_ingest_status
from tests.conftest import add_test_course

client = TestClient(app)


@pytest.fixture(autouse=True)
def _bind_fastapi_db(db_session):
    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


def test_get_ingest_status_queued_job(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename="status-queued.pdf",
        doc_kind="notes",
        status="pending",
        file_path="/tmp/status-queued.pdf",
    )
    db_session.add(document)
    db_session.flush()
    job = enqueue_ingest_job(db_session, document_id=document.id, phase="full")
    db_session.commit()

    status = get_ingest_status(db_session, document.id)
    assert status is not None
    assert status["document_id"] == str(document.id)
    assert status["job_id"] == str(job.id)
    assert status["status"] == "queued"
    assert status["phase"] == "full"
    assert status["progress_pct"] == 0
    assert status["error"] is None
    assert status["document_status"] == "pending"


def test_get_ingest_status_ready_without_job(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename="sync-ready.pdf",
        doc_kind="notes",
        status="ready",
        page_count=10,
        file_path="/tmp/sync-ready.pdf",
    )
    db_session.add(document)
    db_session.commit()

    status = get_ingest_status(db_session, document.id)
    assert status is not None
    assert status["job_id"] is None
    assert status["status"] == "ready"
    assert status["progress_pct"] == 100


def test_api_ingest_status_returns_queued(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL")
    document = Document(
        course_id="PPL",
        filename="api-status.pdf",
        doc_kind="notes",
        status="pending",
        file_path="/tmp/api-status.pdf",
    )
    db_session.add(document)
    db_session.flush()
    job = enqueue_ingest_job(db_session, document_id=document.id, phase="full")
    db_session.commit()

    response = client.get(f"/api/v1/documents/{document.id}/ingest-status")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["status"] == "queued"
    assert body["phase"] == "full"
    assert body["progress_pct"] == 0
    assert body["document_status"] == "pending"


def test_api_ingest_status_404_unknown_document() -> None:
    missing = uuid.uuid4()
    response = client.get(f"/api/v1/documents/{missing}/ingest-status")
    assert response.status_code == 404


def test_api_ingest_status_404_wrong_workspace(db_session) -> None:
    from app.models import Workspace

    other_workspace = Workspace(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(other_workspace)
    db_session.flush()
    add_test_course(db_session, "PPL", "PPL", workspace_id=other_workspace.id)
    document = Document(
        course_id="PPL",
        filename="foreign.pdf",
        doc_kind="notes",
        status="pending",
        file_path="/tmp/foreign.pdf",
    )
    db_session.add(document)
    db_session.commit()

    response = client.get(f"/api/v1/documents/{document.id}/ingest-status")
    assert response.status_code == 404

