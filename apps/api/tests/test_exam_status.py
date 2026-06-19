"""Tests for GET /exam/status unified exam index readiness."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.conftest import add_test_course

from app.main import app
from app.models import Chunk, ChunkEmbedding, ChunkParent, Course, Document, ExamQuestion
from app.services.exam.exam_status import compute_exam_status

client = TestClient(app)

_READABLE_PAST_PAPER_TEXT = (
    "Question on alkanes and thermodynamics for exam preparation. " * 3
)


def test_exam_status_unknown_course_404(db_session) -> None:
    response = client.get("/api/v1/courses/NOPE/exam/status")
    assert response.status_code == 404


def test_exam_status_empty_course(db_session) -> None:
    add_test_course(db_session, "TEST101", "Chemistry")
    db_session.commit()

    result = compute_exam_status(db_session, "TEST101")
    assert result["found"] is True
    assert result["documents_ready"] is False
    assert result["exam_index_ready"] is False
    assert result["heatmap_available"] is False
    assert result["heatmap_source"] == "none"
    assert result["parsed_questions"] == 0
    assert result["question_count_source"] == "none"


def test_exam_status_with_past_paper_and_embeddings(db_session) -> None:
    add_test_course(db_session, "TEST101", "Chemistry")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="TEST101",
            filename="past.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=5,
        )
    )
    db_session.flush()
    parent_id = uuid.uuid4()
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=1,
            page_end=1,
            text=_READABLE_PAST_PAPER_TEXT,
        )
    )
    chunk_id = uuid.uuid4()
    db_session.add(
        Chunk(
            id=chunk_id,
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=0,
            page=1,
            text=_READABLE_PAST_PAPER_TEXT,
            token_count=20,
        )
    )
    db_session.add(
        ChunkEmbedding(
            chunk_id=chunk_id,
            embedding=[0.1] * 384,
            embedding_model="test",
            dimensions=384,
        )
    )
    db_session.commit()

    result = compute_exam_status(db_session, "TEST101")
    assert result["documents_ready"] is True
    assert result["document_count"] == 1
    assert result["chunk_count"] == 1
    assert result["embedded_chunk_count"] == 1
    assert result["embeddings_ready"] is True
    assert result["exam_index_ready"] is True
    assert result["readable_pages"] == 1
    assert result["heatmap_available"] is True
    assert result["heatmap_source"] == "keyword"


def test_exam_status_parsed_questions_from_db(db_session) -> None:
    add_test_course(db_session, "TEST101", "Chemistry")
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="TEST101",
            filename="past.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=5,
        )
    )
    db_session.add(
        ExamQuestion(
            document_id=doc_id,
            course_id="TEST101",
            page=1,
            prompt_text="Define alkanes.",
            unit="1",
            section_title="Alkanes",
            extraction_method="regex",
        )
    )
    db_session.add(
        ExamQuestion(
            document_id=doc_id,
            course_id="TEST101",
            page=1,
            prompt_text="Explain thermodynamics.",
            unit="1",
            section_title="Thermodynamics",
            extraction_method="seed_import",
        )
    )
    db_session.commit()

    result = compute_exam_status(db_session, "TEST101")
    assert result["parsed_questions"] == 2
    assert result["question_count_source"] == "exam_questions"
    assert result["heatmap_source"] == "parsed"
    assert result["heatmap_available"] is True
    assert result["exam_index_ready"] is False


@patch("app.main.compute_exam_status")
def test_api_exam_status(mock_compute) -> None:
    mock_compute.return_value = {
        "found": True,
        "course_id": "PPL",
        "documents_ready": True,
        "document_count": 1,
        "readable_pages": 20,
        "total_pages": 30,
        "chunk_count": 80,
        "embedded_chunk_count": 80,
        "embeddings_ready": True,
        "parsed_questions": 0,
        "has_pyq_seed": True,
        "exam_index_ready": True,
        "heatmap_available": True,
        "heatmap_source": "seed",
        "source_documents": [],
    }
    response = client.get("/api/v1/courses/PPL/exam/status")
    assert response.status_code == 200
    body = response.json()
    assert body["has_pyq_seed"] is True
    assert body["heatmap_source"] == "seed"
