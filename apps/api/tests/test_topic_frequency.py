"""Tests for PYQ topic frequency (no LLM, no OpenRouter)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.models import Chunk, ChunkParent, Course, Document
from app.services.exam.topic_frequency import compute_topic_frequency, load_seed_questions

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTLINE_PATH = REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml"
SEED_PATH = REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_pyq_seed.yaml"

client = TestClient(app)


def test_ppl_seed_loads_questions() -> None:
    questions, covered, note = load_seed_questions("PPL")
    assert len(questions) == 25
    assert 3 in covered
    assert "partial" in note.lower() or "ocr" in note.lower()


def test_seed_unit_counts(db_session) -> None:
    db_session.add(Course(id="PPL", name="Programming Languages"))
    db_session.add(
        Document(
            id=uuid.uuid4(),
            course_id="PPL",
            filename="PPL previous papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=30,
        )
    )
    db_session.commit()

    result = compute_topic_frequency(
        db_session,
        "PPL",
        outline_path=OUTLINE_PATH,
        seed_path=SEED_PATH,
    )

    assert result["total_questions_estimated"] == 25
    unit_counts = {unit["unit"]: unit["count"] for unit in result["units"]}
    assert unit_counts["1"] == 8
    assert unit_counts["2"] == 3
    assert unit_counts["3"] == 1
    assert unit_counts["4"] == 9
    assert unit_counts["5"] == 4


def test_keyword_matcher_adds_unseeded_page(db_session) -> None:
    db_session.add(Course(id="PPL", name="Programming Languages"))
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="PPL",
            filename="PPL previous papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=30,
        )
    )
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=99,
            page_end=99,
            text="placeholder",
        )
    )
    db_session.add(
        Chunk(
            id=uuid.uuid4(),
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=0,
            page=99,
            text=(
                "Explain short-circuit evaluation with an example and operator associativity. "
                "Include both AND and OR short-circuit behavior in your answer."
            ),
            token_count=20,
        )
    )
    db_session.commit()

    result = compute_topic_frequency(
        db_session,
        "PPL",
        outline_path=OUTLINE_PATH,
        seed_path=SEED_PATH,
    )

    assert result["total_questions_estimated"] == 26
    unit2 = next(u for u in result["units"] if u["unit"] == "2")
    assert unit2["count"] == 4
    section_counts = {s["section_title"]: s["count"] for s in unit2["sections"]}
    assert section_counts["Expressions and Statements & Control Structures"] >= 2
    assert sum(section_counts.values()) == 4


def test_empty_when_no_past_paper(db_session) -> None:
    db_session.add(Course(id="PPL", name="Programming Languages"))
    db_session.commit()

    result = compute_topic_frequency(db_session, "PPL", outline_path=OUTLINE_PATH)

    assert result["total_questions_estimated"] == 0
    assert result["source_documents"] == []
    assert "No past_paper" in result["coverage_note"]


@patch("app.main.compute_topic_frequency")
def test_api_topic_frequency(mock_compute) -> None:
    mock_compute.return_value = {
        "found": True,
        "course_id": "PPL",
        "total_questions_estimated": 25,
        "coverage_note": "partial",
        "units": [],
        "source_documents": [],
    }

    response = client.get("/api/v1/courses/PPL/exam/topic-frequency")
    assert response.status_code == 200
    body = response.json()
    assert body["course_id"] == "PPL"
    assert body["total_questions_estimated"] == 25
    assert "found" not in body


def test_api_unknown_course_404() -> None:
    response = client.get("/api/v1/courses/UNKNOWN/exam/topic-frequency")
    assert response.status_code == 404


def test_exam_service_does_not_import_study_pipeline() -> None:
    import app.services.exam.topic_frequency as topic_frequency

    source = Path(topic_frequency.__file__).read_text(encoding="utf-8")
    assert "run_study_question" not in source
    assert "run_study_query" not in source
    assert "generate_study_answer" not in source


def test_keyword_match_inline_text() -> None:
    from app.services.exam.topic_frequency import _best_keyword_match, _build_keyword_patterns
    from app.services.pdf_extract import load_outline

    outline = load_outline(OUTLINE_PATH)
    patterns = _build_keyword_patterns(outline)
    text = "Discuss parameter passing pass-by-reference and pass-by-value with examples."
    match = _best_keyword_match(text, patterns)
    assert match is not None
    assert match[0] == "3"


def test_source_documents_readable_pages(db_session) -> None:
    db_session.add(Course(id="PPL", name="Programming Languages"))
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="PPL",
            filename="PPL previous papers.pdf",
            doc_kind="past_paper",
            status="ready",
        )
    )
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=3,
            page_end=3,
            text="x",
        )
    )
    long_text = "x" * 150
    db_session.add(
        Chunk(
            id=uuid.uuid4(),
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=0,
            page=3,
            text=long_text,
            token_count=10,
        )
    )
    db_session.add(
        Chunk(
            id=uuid.uuid4(),
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=1,
            page=4,
            text="",
            token_count=0,
        )
    )
    db_session.commit()

    result = compute_topic_frequency(
        db_session,
        "PPL",
        outline_path=OUTLINE_PATH,
        seed_path=SEED_PATH,
    )
    sources = result["source_documents"]
    assert len(sources) == 1
    assert sources[0]["readable_pages"] == [3]
    assert sources[0]["chunk_count"] == 2
