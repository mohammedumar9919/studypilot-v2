"""Tests for generic course outline + topic frequency (Wave 6.5, SP-036)."""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient

from tests.conftest import add_test_course

from app.database import get_session
from app.main import app
from app.models import Chunk, ChunkParent, Course, Document
from app.services.course_outline import build_auto_stub_outline, get_course_outline, save_course_outline
from app.services.exam.topic_frequency import compute_topic_frequency

client = TestClient(app)

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
PPL_OUTLINE_PATH = REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml"
PPL_SEED_PATH = REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_pyq_seed.yaml"


def _override_db(db_session):
    def override_session() -> Generator:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def _seed_chemistry_course(db_session) -> tuple[uuid.UUID, uuid.UUID]:
    notes_id = uuid.uuid4()
    past_id = uuid.uuid4()
    notes_parent = uuid.uuid4()
    past_parent = uuid.uuid4()

    add_test_course(db_session, "TEST101", "Chemistry")
    db_session.add(
        Document(
            id=notes_id,
            course_id="TEST101",
            filename="Chemistry notes.pdf",
            doc_kind="notes",
            status="ready",
            page_count=25,
        )
    )
    db_session.add(
        Document(
            id=past_id,
            course_id="TEST101",
            filename="Chemistry past papers.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=10,
        )
    )
    db_session.add(
        ChunkParent(
            id=notes_parent,
            document_id=notes_id,
            page_start=1,
            page_end=25,
            text="notes",
        )
    )
    db_session.add(
        ChunkParent(
            id=past_parent,
            document_id=past_id,
            page_start=1,
            page_end=10,
            text="past",
        )
    )
    long_text = "x" * 150
    for page in (1, 2, 3):
        db_session.add(
            Chunk(
                id=uuid.uuid4(),
                parent_id=past_parent,
                document_id=past_id,
                chunk_index=page - 1,
                page=page,
                text=long_text,
                token_count=20,
            )
        )
    db_session.commit()
    return notes_id, past_id


def test_auto_stub_outline_from_notes(db_session) -> None:
    _seed_chemistry_course(db_session)

    outline = build_auto_stub_outline(db_session, "TEST101")
    assert outline is not None
    assert len(outline.units) == 1
    assert outline.units[0].title == "Chemistry notes"
    assert len(outline.units[0].sections) >= 2


def test_get_course_outline_auto_stub(db_session) -> None:
    _seed_chemistry_course(db_session)

    result = get_course_outline(db_session, "TEST101")
    assert result is not None
    assert result["outline_source"] == "auto_stub"
    assert result["course_id"] == "TEST101"
    assert len(result["units"]) == 1
    assert result["units"][0]["sections"]


def test_api_course_outline_chemistry(db_session) -> None:
    _seed_chemistry_course(db_session)
    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/TEST101/outline")
    finally:
        _clear_db_override()

    assert response.status_code == 200
    body = response.json()
    assert body["outline_source"] == "auto_stub"
    assert len(body["units"]) >= 1


def test_topic_frequency_chemistry_generic(db_session) -> None:
    _seed_chemistry_course(db_session)

    result = compute_topic_frequency(db_session, "TEST101")
    assert result["total_questions_estimated"] == 3
    assert len(result["units"]) == 1
    assert result["units"][0]["count"] == 3
    assert "keyword" in result["coverage_note"].lower()
    assert len(result["source_documents"]) == 1


def test_topic_frequency_keyword_alkanes(db_session) -> None:
    notes_id, past_id = _seed_chemistry_course(db_session)
    past_parent = db_session.query(ChunkParent).filter_by(document_id=past_id).one()

    db_session.query(Chunk).filter_by(document_id=past_id).delete()
    db_session.add(
        Chunk(
            id=uuid.uuid4(),
            parent_id=past_parent.id,
            document_id=past_id,
            chunk_index=0,
            page=5,
            text=(
                "Explain the structure and reactions of alkanes including methane and ethane. "
                "Include substitution reactions in your answer."
            ),
            token_count=20,
        )
    )
    db_session.commit()

    save_course_outline(
        db_session,
        "TEST101",
        {
            "document": "Chemistry notes.pdf",
            "course": "TEST101",
            "page_index_base": 0,
            "page_count": 25,
            "units": [
                {
                    "id": "1",
                    "title": "Organic Chemistry",
                    "page_start": 0,
                    "page_end": 24,
                    "sections": [
                        {"title": "Alkanes", "page_start": 0, "page_end": 12},
                        {"title": "Alkenes", "page_start": 13, "page_end": 24},
                    ],
                }
            ],
        },
    )

    result = compute_topic_frequency(db_session, "TEST101")
    assert result["total_questions_estimated"] == 1
    unit = result["units"][0]
    section_counts = {section["section_title"]: section["count"] for section in unit["sections"]}
    assert section_counts.get("Alkanes", 0) == 1
    assert section_counts.get("Unclassified", 0) == 0


def test_extracted_outline_resolution(db_session) -> None:
    _seed_chemistry_course(db_session)
    course = db_session.get(Course, "TEST101")
    assert course is not None
    course.outline_data = {
        "document": "Chemistry notes.pdf",
        "course": "TEST101",
        "page_index_base": 0,
        "page_count": 25,
        "outline_source": "extracted",
        "units": [
            {
                "id": "1",
                "title": "Organic Chemistry",
                "page_start": 0,
                "page_end": 24,
                "sections": [
                    {"title": "Thermodynamics", "page_start": 0, "page_end": 12},
                    {"title": "Kinetics", "page_start": 13, "page_end": 24},
                ],
            }
        ],
    }
    db_session.commit()

    result = get_course_outline(db_session, "TEST101")
    assert result is not None
    assert result["outline_source"] == "extracted"
    assert result["units"][0]["sections"][0]["title"] == "Thermodynamics"


def test_uploaded_outline_overrides_auto_stub(db_session) -> None:
    _seed_chemistry_course(db_session)
    payload = {
        "document": "Chemistry notes.pdf",
        "course": "TEST101",
        "page_index_base": 0,
        "page_count": 25,
        "units": [
            {
                "id": "1",
                "title": "Organic Chemistry",
                "page_start": 0,
                "page_end": 24,
                "sections": [
                    {
                        "title": "Alkanes",
                        "page_start": 0,
                        "page_end": 12,
                    },
                    {
                        "title": "Alkenes",
                        "page_start": 13,
                        "page_end": 24,
                    },
                ],
            }
        ],
    }

    saved = save_course_outline(db_session, "TEST101", payload)
    assert saved["outline_source"] == "uploaded"
    assert saved["units"][0]["title"] == "Organic Chemistry"

    fetched = get_course_outline(db_session, "TEST101")
    assert fetched is not None
    assert fetched["outline_source"] == "uploaded"
    assert len(fetched["units"][0]["sections"]) == 2


def test_post_outline_api(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry")
    db_session.commit()
    _override_db(db_session)
    try:
        response = client.post(
            "/api/v1/courses/CHEM/outline",
            json={
                "document": "notes.pdf",
                "page_index_base": 0,
                "page_count": 10,
                "units": [
                    {
                        "id": "1",
                        "title": "Unit 1",
                        "page_start": 0,
                        "page_end": 9,
                        "sections": [
                            {"title": "Intro", "page_start": 0, "page_end": 9},
                        ],
                    }
                ],
            },
        )
    finally:
        _clear_db_override()

    assert response.status_code == 201
    assert response.json()["outline_source"] == "uploaded"


def test_topic_frequency_aggregates_to_units_when_many_sections(db_session) -> None:
    _seed_chemistry_course(db_session)
    sections = [
        {"title": f"Topic {index}", "page_start": index * 2, "page_end": index * 2 + 1}
        for index in range(15)
    ]
    save_course_outline(
        db_session,
        "TEST101",
        {
            "document": "Chemistry notes.pdf",
            "course": "TEST101",
            "page_index_base": 0,
            "page_count": 30,
            "units": [
                {
                    "id": "1",
                    "title": "Organic Chemistry",
                    "page_start": 0,
                    "page_end": 29,
                    "sections": sections,
                }
            ],
        },
    )

    result = compute_topic_frequency(db_session, "TEST101")
    assert result["units"]
    for unit in result["units"]:
        assert "sections" in unit
        assert unit["sections"] == []

    detailed = compute_topic_frequency(db_session, "TEST101", include_section_detail=True)
    assert "sections" in detailed["units"][0]
    assert detailed["units"][0]["sections"]


def test_ppl_still_uses_fixture(db_session) -> None:
    add_test_course(db_session, "PPL", "Programming Languages")
    db_session.commit()

    result = get_course_outline(db_session, "PPL")
    assert result is not None
    assert result["outline_source"] == "fixture"
    assert len(result["units"]) == 5


def test_ppl_topic_frequency_unchanged(db_session) -> None:
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
        outline_path=PPL_OUTLINE_PATH,
        seed_path=PPL_SEED_PATH,
    )
    assert result["total_questions_estimated"] == 25
