"""Tests for PYQ topic frequency (no LLM, no OpenRouter)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from tests.conftest import add_test_course

from app.main import app
from app.models import Chunk, ChunkParent, Course, Document, ExamQuestion
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
    add_test_course(db_session, "PPL", "Programming Languages")
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
    add_test_course(db_session, "PPL", "Programming Languages")
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
    add_test_course(db_session, "PPL", "Programming Languages")
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


def test_exam_questions_beat_keyword_proxy(db_session) -> None:
    """Parsed exam_questions rows take priority over keyword page proxy."""
    add_test_course(db_session, "CHEM", "Chemistry")
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="CHEM",
            filename="Chemistry past papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=10,
        )
    )
    long_text = (
        "Question on alkanes and thermodynamics enthalpy reaction rates catalysts. " * 3
    )
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=1,
            page_end=3,
            text=long_text,
        )
    )
    for page in (1, 2, 3):
        db_session.add(
            Chunk(
                id=uuid.uuid4(),
                parent_id=parent_id,
                document_id=doc_id,
                chunk_index=page - 1,
                page=page,
                text=long_text,
                token_count=30,
            )
        )
    db_session.add(
        ExamQuestion(
            document_id=doc_id,
            course_id="CHEM",
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
            course_id="CHEM",
            page=2,
            prompt_text="Explain enthalpy.",
            unit="1",
            section_title="Enthalpy",
            extraction_method="regex",
        )
    )
    db_session.commit()

    outline = {
        "document": "Chemistry notes.pdf",
        "page_index_base": 0,
        "page_count": 50,
        "units": [
            {
                "id": "1",
                "title": "Thermodynamics",
                "page_start": 0,
                "page_end": 49,
                "sections": [
                    {"title": "Alkanes", "page_start": 0, "page_end": 24},
                    {"title": "Enthalpy", "page_start": 25, "page_end": 49},
                ],
            }
        ],
    }
    from app.services.course_outline import save_course_outline

    save_course_outline(db_session, "CHEM", outline)

    result = compute_topic_frequency(db_session, "CHEM")
    assert result["total_questions_estimated"] == 2
    assert "exam_questions" in result["coverage_note"]
    assert "2 via regex" in result["coverage_note"]
    unit1 = next(unit for unit in result["units"] if unit["unit"] == "1")
    assert unit1["count"] == 2


def test_source_documents_readable_pages(db_session) -> None:
    add_test_course(db_session, "PPL", "Programming Languages")
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
