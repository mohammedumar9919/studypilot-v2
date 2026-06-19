"""Tests for Course Map promotion eligibility and promote API."""

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
from app.services.course_map import get_course_map_eligibility, promote_course_map
from app.services.course_outline import resolve_course_outline
from app.services.pdf_extract import DocumentOutline, OutlineSection, OutlineUnit
from app.services.study_layout import get_study_layout
from tests.conftest import add_test_course

client = TestClient(app)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def _sample_syllabus_outline(*, course_id: str = "CHEM") -> DocumentOutline:
    return DocumentOutline(
        document="syllabus.pdf",
        course=course_id,
        page_index_base=0,
        page_count=80,
        units=[
            OutlineUnit(
                id="1",
                title="Unit 1 Thermodynamics",
                page_start=0,
                page_end=11,
                sections=[OutlineSection(title="Thermodynamics", page_start=0, page_end=11)],
            ),
            OutlineUnit(
                id="2",
                title="Unit 2 Atomic Structure",
                page_start=12,
                page_end=24,
                sections=[OutlineSection(title="Atomic Structure", page_start=12, page_end=24)],
            ),
        ],
    )


def _add_syllabus_document(
    db_session: Session,
    *,
    course_id: str = "CHEM",
    file_path: Path,
    filename: str = "syllabus.pdf",
) -> Document:
    document = Document(
        id=uuid.uuid4(),
        course_id=course_id,
        filename=filename,
        doc_kind="syllabus",
        status="ready",
        file_path=str(file_path),
        extraction_quality={"upload_intent": "syllabus"},
    )
    db_session.add(document)
    return document


def test_eligibility_high_outline_requires_syllabus(db_session, tmp_path) -> None:
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={"outline_quality": "high", "outline_source": "extracted", "units": []},
    )
    db_session.commit()

    result = get_course_map_eligibility(db_session, "CHEM")
    assert result is not None
    assert result["eligible"] is False
    assert result["reason"] == "no_syllabus_document"


def test_eligibility_high_outline_with_syllabus(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={
            "outline_quality": "high",
            "outline_source": "extracted",
            "units": [{"id": "1", "title": "Unit 1", "page_start": 0, "page_end": 10, "sections": []}],
        },
    )
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    result = get_course_map_eligibility(db_session, "CHEM")
    assert result is not None
    assert result["eligible"] is True
    assert result["syllabus_filename"] == "syllabus.pdf"
    assert result["outline_preview"]["unit_count"] == 1


@patch("app.services.course_outline._extract_syllabus_outline")
def test_eligibility_syllabus_dry_run(mock_extract, db_session, tmp_path) -> None:
    mock_extract.return_value = (_sample_syllabus_outline(), "chapter", "medium", "syllabus_block")
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    result = get_course_map_eligibility(db_session, "CHEM")
    assert result is not None
    assert result["eligible"] is True
    assert result["outline_quality"] == "medium"
    assert result["outline_preview"]["unit_count"] == 2


def test_eligibility_syllabus_intent_alone_not_eligible(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "notes.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.add(
        Document(
            id=uuid.uuid4(),
            course_id="CHEM",
            filename="notes.pdf",
            doc_kind="notes",
            status="ready",
            file_path=str(syllabus_path),
            extraction_quality={"upload_intent": "syllabus"},
        )
    )
    db_session.commit()

    with patch(
        "app.services.course_outline._extract_syllabus_outline",
        side_effect=ValueError("outline_extraction_failed"),
    ):
        result = get_course_map_eligibility(db_session, "CHEM")

    assert result is not None
    assert result["eligible"] is False
    assert result["reason"] == "no_outline"


def test_eligibility_not_eligible_low_outline(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={"outline_quality": "low", "outline_source": "auto_stub"},
    )
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    with patch(
        "app.services.course_outline._extract_syllabus_outline",
        side_effect=ValueError("outline_quality_low"),
    ):
        result = get_course_map_eligibility(db_session, "CHEM")

    assert result is not None
    assert result["eligible"] is False
    assert result["reason"] == "outline_quality_not_high"


def test_eligibility_already_mapped_ppl(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL", structure_mode="mapped")
    db_session.commit()

    result = get_course_map_eligibility(db_session, "PPL")
    assert result is not None
    assert result["eligible"] is False
    assert result["structure_mode"] == "mapped"
    assert result["reason"] == "already_mapped"


@patch("app.services.course_map.build_outline_for_promotion")
def test_promote_sets_mapped(mock_build, db_session, tmp_path) -> None:
    mock_build.return_value = {
        "outline_source": "extracted",
        "outline_quality": "high",
        "unit_count": 2,
        "unit_titles": ["Unit 1 Thermodynamics", "Unit 2 Atomic Structure"],
    }
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    result = promote_course_map(db_session, "CHEM")
    assert result["course"].structure_mode == "mapped"
    assert result["promoted"] is True
    assert result["outline_summary"]["unit_count"] == 2
    mock_build.assert_any_call(db_session, "CHEM", dry_run=False)
    assert mock_build.call_count == 2


def test_promote_idempotent_when_already_mapped(db_session) -> None:
    add_test_course(
        db_session,
        "PPL",
        "PPL",
        structure_mode="mapped",
        outline_data={
            "outline_source": "extracted",
            "outline_quality": "high",
            "units": [{"id": "1", "title": "Unit 1", "page_start": 0, "page_end": 10, "sections": []}],
        },
    )
    db_session.commit()

    result = promote_course_map(db_session, "PPL")
    assert result["course"].structure_mode == "mapped"
    assert result["promoted"] is False
    assert result["repaired"] is False


def test_promote_rejects_ineligible(db_session) -> None:
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={"outline_quality": "medium"},
    )
    db_session.commit()

    with pytest.raises(ValueError, match="not eligible"):
        promote_course_map(db_session, "CHEM")


def test_study_layout_promotion_hint_when_eligible_corpus(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={"outline_quality": "high", "outline_source": "extracted", "units": []},
    )
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    layout = get_study_layout(db_session, "CHEM")
    assert layout is not None
    assert layout["mode"] == "corpus"
    assert layout["structure_mode"] == "corpus"
    assert "promotion_hint" in layout


def test_study_layout_no_promotion_hint_when_organized(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="organized",
        outline_data={"outline_quality": "high", "outline_source": "extracted", "units": []},
    )
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    layout = get_study_layout(db_session, "CHEM")
    assert layout is not None
    assert layout["structure_mode"] == "organized"
    assert "promotion_hint" not in layout


@patch("app.services.course_map.build_outline_for_promotion")
def test_api_course_map_promote(mock_build, db_session, tmp_path) -> None:
    mock_build.return_value = {
        "outline_source": "extracted",
        "outline_quality": "high",
        "unit_count": 2,
        "unit_titles": ["Unit 1 Thermodynamics", "Unit 2 Atomic Structure"],
    }
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post("/api/v1/courses/CHEM/course-map/promote")
        assert response.status_code == 200
        body = response.json()
        assert body["structure_mode"] == "mapped"
        assert body["mode"] == "mapped"
        assert body["promoted"] is True
        assert body["outline_summary"]["unit_count"] == 2
    finally:
        _clear_db_override()


def test_api_course_map_eligibility(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(
        db_session,
        "CHEM",
        "Chemistry",
        structure_mode="corpus",
        outline_data={"outline_quality": "high", "outline_source": "extracted", "units": []},
    )
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/CHEM/course-map-eligibility")
        assert response.status_code == 200
        body = response.json()
        assert body["eligible"] is True
        assert body["outline_quality"] == "high"
        assert body["syllabus_filename"] == "syllabus.pdf"
    finally:
        _clear_db_override()


def test_api_promote_without_syllabus_returns_422(db_session) -> None:
    add_test_course(db_session, "CHEM", "Chemistry", structure_mode="corpus")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post("/api/v1/courses/CHEM/course-map/promote")
        assert response.status_code == 422
    finally:
        _clear_db_override()


def test_api_cn_demote_to_corpus(db_session) -> None:
    add_test_course(db_session, "CN", "CN", structure_mode="mapped")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.patch(
            "/api/v1/courses/CN/structure-mode",
            json={"structure_mode": "corpus"},
        )
        assert response.status_code == 200
        assert response.json()["structure_mode"] == "corpus"
    finally:
        _clear_db_override()


def test_api_ppl_demote_still_400(db_session) -> None:
    add_test_course(db_session, "PPL", "PPL", structure_mode="mapped")
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.patch(
            "/api/v1/courses/PPL/structure-mode",
            json={"structure_mode": "corpus"},
        )
        assert response.status_code == 400
    finally:
        _clear_db_override()


def test_mapped_syllabus_course_skips_auto_stub(db_session, tmp_path) -> None:
    syllabus_path = tmp_path / "syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    add_test_course(
        db_session,
        "CN",
        "Computer Networks",
        structure_mode="mapped",
        outline_data={
            "outline_source": "extracted",
            "outline_quality": "medium",
            "document": "syllabus.pdf",
            "page_index_base": 0,
            "page_count": 80,
            "units": [
                {
                    "id": "1",
                    "title": "Unit 1",
                    "page_start": 0,
                    "page_end": 10,
                    "sections": [],
                }
            ],
        },
    )
    _add_syllabus_document(db_session, course_id="CN", file_path=syllabus_path)
    for index in range(1, 6):
        db_session.add(
            Document(
                id=uuid.uuid4(),
                course_id="CN",
                filename=f"unit{index}.pdf",
                doc_kind="notes",
                status="ready",
                file_path=str(tmp_path / f"unit{index}.pdf"),
                page_count=20,
            )
        )
    db_session.commit()

    outline, source = resolve_course_outline(db_session, "CN")
    assert source == "extracted"
    assert outline is not None
    assert len(outline.units) == 1
