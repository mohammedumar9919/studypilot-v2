"""Tests for course structure schema and APIs (SP-053a)."""

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
from app.services.course_structure import (
    _preview_units_from_parser,
    confirm_course_structure,
    get_course_structure,
    import_pasted_structure,
    import_syllabus_structure,
    parse_pasted_structure,
)
from app.services.pdf_extract import ExtractionResult, PageText

client = TestClient(app)

CN_ENGINEERING_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "syllabus" / "cn_engineering_roman_units.txt"
)


def _override_db(db_session: Session) -> None:
    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def _cn_engineering_pages() -> list[PageText]:
    text = CN_ENGINEERING_FIXTURE.read_text(encoding="utf-8")
    split_at = text.index("UNIT - III")
    page_one = text[:split_at].strip()
    page_two = text[split_at:].strip()
    return [
        PageText(page=1, text=page_one, char_count=len(page_one)),
        PageText(page=2, text=page_two, char_count=len(page_two)),
    ]


def _mock_cn_extraction() -> ExtractionResult:
    pages = _cn_engineering_pages()
    return ExtractionResult(
        pages=pages,
        page_count=len(pages),
        total_chars=sum(page.char_count for page in pages),
        nonempty_pages=len(pages),
        ocr_pages=0,
        quality_flags={"native_text_ratio": 1.0},
    )


def _add_syllabus_document(
    db_session: Session,
    *,
    course_id: str = "CN",
    file_path: Path,
    filename: str = "CN syllabus.pdf",
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


def test_parse_pasted_structure_units_and_indented_subtopics() -> None:
    text = """Unit 1 Networks
  Routing basics
  - Switching fundamentals
Unit 2 Data Link
  Framing
"""
    units = parse_pasted_structure(text)
    assert len(units) == 2
    assert units[0]["title"] == "Unit 1 Networks"
    assert units[0]["subtopics"] == ["Routing basics", "Switching fundamentals"]
    assert "parts" not in units[0]
    assert units[1]["title"] == "Unit 2 Data Link"
    assert units[1]["subtopics"] == ["Framing"]


def test_parse_pasted_structure_three_level_parts_and_comma_topics() -> None:
    text = """Unit 1 Thermodynamics
  Chapter 1
    Heat, Work
  Chapter 2
    Entropy
Unit 2 Atoms
  Orbitals
"""
    units = parse_pasted_structure(text)
    assert len(units) == 2
    assert units[0]["parts"] == [
        {"title": "Chapter 1", "subtopics": ["Heat", "Work"]},
        {"title": "Chapter 2", "subtopics": ["Entropy"]},
    ]
    assert units[1]["subtopics"] == ["Orbitals"]
    assert "parts" not in units[1]


def test_preview_units_from_parser_v2_parts_shape() -> None:
    raw_units = [
        {
            "unit_title": "Unit 1 Networks",
            "parts": [
                {"part_title": "Layer 1", "subtopic_titles": ["Physical", "Signals"]},
                {"title": "Layer 2", "subtopics": ["Framing"]},
            ],
        },
        {"title": "Unit 2 Transport", "subtopics": ["TCP", "UDP"]},
    ]
    preview = _preview_units_from_parser(raw_units)
    assert preview[0]["parts"][0]["subtopics"] == ["Physical", "Signals"]
    assert preview[0]["parts"][1]["title"] == "Layer 2"
    assert preview[1]["subtopics"] == ["TCP", "UDP"]


@patch("app.services.course_structure._parse_syllabus_pdf")
def test_import_syllabus_preview_nested_parts(mock_parse, db_session) -> None:
    mock_parse.return_value = (
        [
            {
                "title": "Unit 1",
                "parts": [{"title": "Part A", "subtopics": ["Topic 1"]}],
            }
        ],
        None,
    )
    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="corpus"))
    db_session.commit()

    with patch(
        "app.services.course_structure._resolve_syllabus_document",
        return_value=Document(
            id=uuid.uuid4(),
            course_id="CN",
            filename="CN syllabus.pdf",
            doc_kind="syllabus",
            status="ready",
            file_path="ignored.pdf",
        ),
    ):
        result = import_syllabus_structure(db_session, "CN")

    assert result is not None
    assert result["units"][0]["parts"][0]["title"] == "Part A"


def test_confirm_persists_nested_parts(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="corpus"))
    db_session.commit()

    confirmed = confirm_course_structure(
        db_session,
        "CHEM",
        [
            {
                "title": "Unit 1 Thermodynamics",
                "parts": [
                    {"title": "Laws", "subtopics": ["Heat", "Work"]},
                    {"title": "Cycles", "subtopics": ["Carnot"]},
                ],
            },
            {"title": "Unit 2 Atoms", "subtopics": ["Orbitals"]},
        ],
    )
    assert confirmed is not None
    assert confirmed["units"][0]["parts"][0]["title"] == "Laws"
    assert confirmed["units"][0]["parts"][0]["subtopics"][0]["title"] == "Heat"
    assert confirmed["units"][0]["parts"][0]["document_ids"] == []
    assert "subtopics" not in confirmed["units"][0]
    assert confirmed["units"][1]["subtopics"][0]["title"] == "Orbitals"
    assert "parts" not in confirmed["units"][1]


def test_api_import_paste_nested_and_confirm(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="corpus"))
    db_session.commit()

    _override_db(db_session)
    try:
        preview = client.post(
            "/api/v1/courses/CHEM/structure/import-paste",
            json={
                "text": (
                    "Unit 1 Thermodynamics\n"
                    "  Chapter 1\n"
                    "    Heat, Work\n"
                    "Unit 2 Atoms\n"
                    "  Orbitals"
                )
            },
        )
        assert preview.status_code == 200
        preview_body = preview.json()
        assert preview_body["units"][0]["parts"][0]["subtopics"] == ["Heat", "Work"]

        confirm = client.post(
            "/api/v1/courses/CHEM/structure/confirm",
            json={"units": preview_body["units"]},
        )
        assert confirm.status_code == 200
        confirmed = confirm.json()
        assert confirmed["units"][0]["parts"][0]["subtopics"][0]["title"] == "Heat"
        assert confirmed["units"][1]["subtopics"][0]["title"] == "Orbitals"
    finally:
        _clear_db_override()


def test_parse_pasted_structure_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text must not be empty"):
        parse_pasted_structure("   \n")


def test_import_paste_preview(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="corpus"))
    db_session.commit()

    result = import_pasted_structure(
        db_session,
        "CHEM",
        "Unit 1 Thermodynamics\n  Heat and work",
    )
    assert result == {
        "preview": True,
        "units": [{"title": "Unit 1 Thermodynamics", "subtopics": ["Heat and work"]}],
    }


@patch("app.services.pdf_extract.extract_pdf")
def test_import_syllabus_cn_preview_five_units(mock_extract, db_session, tmp_path) -> None:
    mock_extract.return_value = _mock_cn_extraction()
    syllabus_path = tmp_path / "CN syllabus.pdf"
    syllabus_path.write_bytes(CN_ENGINEERING_FIXTURE.read_bytes())
    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="corpus"))
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    result = import_syllabus_structure(db_session, "CN")
    assert result is not None
    assert result["preview"] is True
    assert len(result["units"]) == 5
    titles = " ".join(unit["title"].lower() for unit in result["units"])
    assert "transport layer" in titles
    assert "application layer" in titles
    assert all(unit["subtopics"] for unit in result["units"])


def test_confirm_persists_structure_and_sets_organized(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="corpus"))
    db_session.commit()

    confirmed = confirm_course_structure(
        db_session,
        "CHEM",
        [
            {"title": "Unit 1 Thermodynamics", "subtopics": ["Heat", "Work"]},
            {"title": "Unit 2 Atomic Structure", "subtopics": []},
        ],
    )
    assert confirmed is not None
    assert confirmed["course_id"] == "CHEM"
    assert len(confirmed["units"]) == 2
    assert confirmed["units"][0]["title"] == "Unit 1 Thermodynamics"
    assert confirmed["units"][0]["sort_order"] == 0
    assert confirmed["units"][0]["document_ids"] == []
    assert len(confirmed["units"][0]["subtopics"]) == 2
    assert confirmed["units"][0]["subtopics"][0]["title"] == "Heat"

    course = db_session.get(Course, "CHEM")
    assert course is not None
    assert course.structure_mode == "organized"

    fetched = get_course_structure(db_session, "CHEM")
    assert fetched == confirmed


def test_confirm_replaces_existing_structure(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="organized"))
    db_session.commit()

    confirm_course_structure(
        db_session,
        "CHEM",
        [{"title": "Old Unit", "subtopics": ["Legacy"]}],
    )
    confirmed = confirm_course_structure(
        db_session,
        "CHEM",
        [{"title": "New Unit", "subtopics": ["Fresh"]}],
    )
    assert confirmed is not None
    assert len(confirmed["units"]) == 1
    assert confirmed["units"][0]["title"] == "New Unit"
    assert confirmed["units"][0]["subtopics"][0]["title"] == "Fresh"


def test_get_course_structure_unknown_course(db_session) -> None:
    assert get_course_structure(db_session, "UNKNOWN") is None


def test_api_get_structure_empty(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="corpus"))
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/CHEM/structure")
        assert response.status_code == 200
        body = response.json()
        assert body["course_id"] == "CHEM"
        assert body["units"] == []
    finally:
        _clear_db_override()


def test_api_import_paste_and_confirm_flow(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry", structure_mode="corpus"))
    db_session.commit()

    _override_db(db_session)
    try:
        preview = client.post(
            "/api/v1/courses/CHEM/structure/import-paste",
            json={"text": "Unit 1 Thermodynamics\n  Heat\nUnit 2 Atoms\n  Orbitals"},
        )
        assert preview.status_code == 200
        preview_body = preview.json()
        assert preview_body["preview"] is True
        assert len(preview_body["units"]) == 2

        confirm = client.post(
            "/api/v1/courses/CHEM/structure/confirm",
            json={"units": preview_body["units"]},
        )
        assert confirm.status_code == 200
        confirmed = confirm.json()
        assert len(confirmed["units"]) == 2
        assert confirmed["units"][0]["subtopics"][0]["title"] == "Heat"

        fetched = client.get("/api/v1/courses/CHEM/structure")
        assert fetched.status_code == 200
        assert fetched.json() == confirmed
    finally:
        _clear_db_override()


@patch("app.services.pdf_extract.extract_pdf")
def test_api_import_syllabus_cn_five_units(mock_extract, db_session, tmp_path) -> None:
    mock_extract.return_value = _mock_cn_extraction()
    syllabus_path = tmp_path / "CN syllabus.pdf"
    syllabus_path.write_bytes(CN_ENGINEERING_FIXTURE.read_bytes())
    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="corpus"))
    _add_syllabus_document(db_session, file_path=syllabus_path)
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post("/api/v1/courses/CN/structure/import-syllabus", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["preview"] is True
        assert len(body["units"]) == 5
    finally:
        _clear_db_override()


def test_api_import_syllabus_no_document_422(db_session) -> None:
    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="corpus"))
    db_session.commit()

    _override_db(db_session)
    try:
        response = client.post("/api/v1/courses/CN/structure/import-syllabus", json={})
        assert response.status_code == 422
        assert response.json()["detail"] == "syllabus_document_not_found"
    finally:
        _clear_db_override()


def test_api_structure_404(db_session) -> None:
    _override_db(db_session)
    try:
        response = client.get("/api/v1/courses/UNKNOWN/structure")
        assert response.status_code == 404
    finally:
        _clear_db_override()
