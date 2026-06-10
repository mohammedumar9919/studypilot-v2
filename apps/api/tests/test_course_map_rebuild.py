"""Tests for Course Map rebuild-outline and stuck-CN repair paths."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_session
from app.main import app
from app.models import Course, Document
from app.services.course_map import promote_course_map, rebuild_course_map_outline
from app.services.course_outline import get_course_outline
from app.services.study_topics import update_structure_mode

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def _seed_stuck_cn(db_session: Session, tmp_path: Path) -> None:
    syllabus_path = tmp_path / "CN syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    db_session.add(
        Course(
            id="CN",
            name="Computer Networks",
            structure_mode="mapped",
            outline_data=None,
        )
    )
    db_session.add(
        Document(
            id=uuid.uuid4(),
            course_id="CN",
            filename="CN syllabus.pdf",
            doc_kind="syllabus",
            status="ready",
            file_path=str(syllabus_path),
            extraction_quality={"upload_intent": "syllabus"},
        )
    )
    db_session.commit()


def _persist_mock_outline(session: Session, course_id: str) -> None:
    course = session.get(Course, course_id)
    if course is None:
        return
    course.outline_data = {
        "outline_source": "extracted",
        "outline_quality": "medium",
        "document": "CN syllabus.pdf",
        "page_index_base": 0,
        "page_count": 80,
        "units": [
            {
                "id": str(index),
                "title": title,
                "page_start": index * 10,
                "page_end": index * 10 + 9,
                "sections": [],
            }
            for index, title in enumerate(
                [
                    "Unit 1 Thermodynamics",
                    "Unit 2 Atomic Structure",
                    "Unit 3 Chemical Bonding",
                    "Unit 4 Equilibrium",
                    "Unit 5 Electrochemistry",
                ],
                start=1,
            )
        ],
    }
    session.flush()


@patch("app.services.course_map.build_outline_for_promotion")
def test_rebuild_outline_for_stuck_cn(mock_build, db_session, tmp_path) -> None:
    mock_build.return_value = {
        "outline_source": "extracted",
        "outline_quality": "medium",
        "unit_count": 5,
        "unit_titles": ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"],
    }
    _seed_stuck_cn(db_session, tmp_path)

    result = rebuild_course_map_outline(db_session, "CN")
    assert result["rebuilt"] is True
    assert result["outline_summary"]["unit_count"] == 5
    mock_build.assert_called_once_with(db_session, "CN", dry_run=False)

    course = db_session.get(Course, "CN")
    assert course is not None
    assert course.structure_mode == "mapped"


@patch("app.services.course_map.build_outline_for_promotion")
def test_promote_repairs_stuck_mapped_cn(mock_build, db_session, tmp_path) -> None:
    mock_build.return_value = {
        "outline_source": "extracted",
        "outline_quality": "medium",
        "unit_count": 5,
        "unit_titles": ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"],
    }
    _seed_stuck_cn(db_session, tmp_path)

    result = promote_course_map(db_session, "CN")
    assert result["promoted"] is False
    assert result["repaired"] is True
    assert result["outline_summary"]["unit_count"] == 5


@patch("app.services.course_map.build_outline_for_promotion")
def test_rebuild_outline_makes_get_outline_available(mock_build, db_session, tmp_path) -> None:
    def _build_side_effect(session, course_id, *, dry_run=False):
        if not dry_run:
            _persist_mock_outline(session, course_id)
        return {
            "outline_source": "extracted",
            "outline_quality": "medium",
            "unit_count": 5,
            "unit_titles": ["Unit 1 Thermodynamics", "Unit 2 Atomic Structure"],
        }

    mock_build.side_effect = _build_side_effect
    _seed_stuck_cn(db_session, tmp_path)

    rebuild_course_map_outline(db_session, "CN")
    outline = get_course_outline(db_session, "CN")
    assert outline is not None
    assert outline["outline_source"] == "extracted"
    assert len(outline["units"]) == 5


def test_cn_mapped_can_demote_to_corpus(db_session) -> None:
    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="mapped"))
    db_session.commit()

    course = update_structure_mode(db_session, "CN", "corpus")
    assert course.structure_mode == "corpus"


def test_ppl_fixture_cannot_demote(db_session) -> None:
    db_session.add(Course(id="PPL", name="PPL", structure_mode="mapped"))
    db_session.commit()

    with pytest.raises(ValueError, match="Cannot demote mapped fixture course"):
        update_structure_mode(db_session, "PPL", "corpus")


@patch("app.main.rebuild_course_map_outline")
def test_api_rebuild_outline(mock_rebuild, db_session) -> None:
    db_session.add(Course(id="CN", name="CN", structure_mode="mapped"))
    db_session.commit()

    mock_rebuild.return_value = {
        "rebuilt": True,
        "outline_summary": {
            "unit_count": 5,
            "unit_titles": ["Unit 1"],
            "outline_quality": "medium",
            "outline_source": "extracted",
        },
    }

    _override_db(db_session)
    try:
        response = client.post("/api/v1/courses/CN/course-map/rebuild-outline")
        assert response.status_code == 200
        body = response.json()
        assert body["rebuilt"] is True
        assert body["outline_summary"]["unit_count"] == 5
    finally:
        _clear_db_override()


def test_api_rebuild_outline_no_syllabus_422(db_session) -> None:
    db_session.add(Course(id="CN", name="CN", structure_mode="mapped"))
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post("/api/v1/courses/CN/course-map/rebuild-outline")
        assert response.status_code == 422
    finally:
        _clear_db_override()
