"""Syllabus-driven Course Map promotion — CN-style UAT regression tests."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models import Course, Document
from app.services.course_map import promote_course_map, rebuild_course_map_outline
from app.services.course_outline import build_outline_for_promotion, get_course_outline, resolve_course_outline
from app.services.pdf_extract import DocumentOutline, OutlineSection, OutlineUnit
from app.services.study_topics import assign_document_topic, create_study_topic
from tests.test_toc_extraction import (
    _cn_engineering_syllabus_pages,
    _syllabus_five_unit_toc_pages as syllabus_toc_pages,
)


def _five_unit_outline(*, course_id: str = "CN") -> DocumentOutline:
    titles = [
        "Unit 1 Thermodynamics",
        "Unit 2 Atomic Structure",
        "Unit 3 Chemical Bonding",
        "Unit 4 Equilibrium",
        "Unit 5 Electrochemistry",
    ]
    units: list[OutlineUnit] = []
    start = 0
    for index, title in enumerate(titles, start=1):
        end = start + 10
        units.append(
            OutlineUnit(
                id=str(index),
                title=title,
                page_start=start,
                page_end=end,
                sections=[OutlineSection(title=title, page_start=start, page_end=end)],
            )
        )
        start = end + 1
    return DocumentOutline(
        document="CN syllabus.pdf",
        course=course_id,
        page_index_base=0,
        page_count=80,
        units=units,
    )


def _seed_cn_course(db_session: Session, tmp_path: Path) -> None:
    syllabus_path = tmp_path / "CN syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")

    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="organized"))
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

    for index in range(1, 6):
        unit_path = tmp_path / f"unit{index}.pdf"
        unit_path.write_bytes(b"%PDF-1.4")
        db_session.add(
            Document(
                id=uuid.uuid4(),
                course_id="CN",
                filename=f"unit{index}.pdf",
                doc_kind="notes",
                status="ready",
                file_path=str(unit_path),
                page_count=20,
            )
        )
    db_session.commit()


@patch("app.services.course_outline.extract_pdf")
@patch("app.services.course_outline.extract_outline_from_pdf")
def test_promote_extracts_syllabus_not_filename_stubs(
    mock_extract_outline,
    mock_extract_pdf,
    db_session,
    tmp_path,
) -> None:
    _seed_cn_course(db_session, tmp_path)
    pages = syllabus_toc_pages()
    mock_extract_pdf.return_value = type(
        "Extraction",
        (),
        {"pages": pages, "page_count": 80, "nonempty_pages": 1},
    )()
    mock_extract_outline.return_value = (_five_unit_outline(), "chapter", "medium")

    result = promote_course_map(db_session, "CN")
    assert result["promoted"] is True
    assert result["outline_summary"]["unit_count"] == 5

    outline, source = resolve_course_outline(db_session, "CN")
    assert source == "extracted"
    assert outline is not None
    assert len(outline.units) == 5


@patch("app.services.course_outline.extract_pdf")
@patch("app.services.course_outline.extract_outline_from_pdf")
def test_promote_merges_topic_documents_into_units(
    mock_extract_outline,
    mock_extract_pdf,
    db_session,
    tmp_path,
) -> None:
    _seed_cn_course(db_session, tmp_path)
    pages = syllabus_toc_pages()
    mock_extract_pdf.return_value = type(
        "Extraction",
        (),
        {"pages": pages, "page_count": 80, "nonempty_pages": 1},
    )()
    mock_extract_outline.return_value = (_five_unit_outline(), "chapter", "high")

    topic_titles = [
        "Thermodynamics",
        "Atomic Structure",
        "Chemical Bonding",
        "Equilibrium",
        "Electrochemistry",
    ]
    topics = [
        create_study_topic(db_session, "CN", title=title, sort_order=index)
        for index, title in enumerate(topic_titles)
    ]
    unit_docs = (
        db_session.query(Document)
        .filter(Document.course_id == "CN", Document.doc_kind == "notes")
        .order_by(Document.filename)
        .all()
    )
    for topic, document in zip(topics, unit_docs, strict=True):
        assign_document_topic(db_session, document.id, topic_id=topic.id)

    promote_course_map(db_session, "CN")
    course = db_session.get(Course, "CN")
    assert course is not None
    units = course.outline_data["units"]
    assert len(units) == 5
    assert all("assigned_document_ids" in unit for unit in units)
    assigned = {doc_id for unit in units for doc_id in unit["assigned_document_ids"]}
    assert len(assigned) == 5


@patch("app.services.course_outline.extract_pdf")
@patch("app.services.course_outline.extract_outline_from_pdf")
def test_build_outline_rejects_low_quality(
    mock_extract_outline,
    mock_extract_pdf,
    db_session,
    tmp_path,
) -> None:
    _seed_cn_course(db_session, tmp_path)
    mock_extract_pdf.return_value = type(
        "Extraction",
        (),
        {"pages": [], "page_count": 1, "nonempty_pages": 0},
    )()
    mock_extract_outline.return_value = (_five_unit_outline(), "page_stub", "low")

    with pytest.raises(ValueError, match="outline_quality_low"):
        build_outline_for_promotion(db_session, "CN", dry_run=True)


def test_build_outline_requires_syllabus_document(db_session) -> None:
    db_session.add(Course(id="CN", name="Computer Networks", structure_mode="organized"))
    db_session.commit()

    with pytest.raises(ValueError, match="syllabus_document_not_found"):
        build_outline_for_promotion(db_session, "CN", dry_run=True)


@patch("app.services.course_outline.extract_pdf")
@patch("app.services.course_outline.extract_outline_from_pdf")
def test_find_syllabus_prefers_doc_kind(
    mock_extract_outline,
    mock_extract_pdf,
    db_session,
    tmp_path,
) -> None:
    syllabus_path = tmp_path / "CN syllabus.pdf"
    notes_path = tmp_path / "notes with syllabus keyword.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    notes_path.write_bytes(b"%PDF-1.4")
    db_session.add(Course(id="CN", name="CN", structure_mode="organized"))
    db_session.add_all(
        [
            Document(
                id=uuid.uuid4(),
                course_id="CN",
                filename=notes_path.name,
                doc_kind="notes",
                status="ready",
                file_path=str(notes_path),
                extraction_quality={"upload_intent": "syllabus"},
            ),
            Document(
                id=uuid.uuid4(),
                course_id="CN",
                filename=syllabus_path.name,
                doc_kind="syllabus",
                status="ready",
                file_path=str(syllabus_path),
            ),
        ]
    )
    db_session.commit()

    mock_extract_pdf.return_value = type(
        "Extraction",
        (),
        {"pages": syllabus_toc_pages(), "page_count": 80, "nonempty_pages": 1},
    )()
    mock_extract_outline.return_value = (_five_unit_outline(), "chapter", "medium")

    summary = build_outline_for_promotion(db_session, "CN", dry_run=True)
    assert summary["unit_count"] == 5

    course = db_session.get(Course, "CN")
    assert course is not None
    assert course.outline_data is None


@patch("app.services.course_outline.extract_pdf")
@patch("app.services.course_outline.extract_outline_from_pdf")
def test_stuck_cn_promote_repairs_outline(
    mock_extract_outline,
    mock_extract_pdf,
    db_session,
    tmp_path,
) -> None:
    """Pre-052.1 CN: mapped with null outline_data → promote repairs via syllabus."""
    syllabus_path = tmp_path / "CN syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    db_session.add(
        Course(id="CN", name="Computer Networks", structure_mode="mapped", outline_data=None)
    )
    db_session.add(
        Document(
            id=uuid.uuid4(),
            course_id="CN",
            filename="CN syllabus.pdf",
            doc_kind="syllabus",
            status="ready",
            file_path=str(syllabus_path),
        )
    )
    db_session.commit()

    pages = syllabus_toc_pages()
    mock_extract_pdf.return_value = type(
        "Extraction",
        (),
        {"pages": pages, "page_count": 80, "nonempty_pages": 1},
    )()
    mock_extract_outline.return_value = (_five_unit_outline(), "chapter", "medium")

    result = promote_course_map(db_session, "CN")
    assert result["promoted"] is False
    assert result["repaired"] is True
    assert result["outline_summary"]["unit_count"] == 5

    outline, source = resolve_course_outline(db_session, "CN")
    assert source == "extracted"
    assert outline is not None
    assert len(outline.units) == 5


@patch("app.services.course_outline.extract_pdf")
def test_rebuild_outline_uses_engineering_syllabus_fixture(mock_extract_pdf, db_session, tmp_path) -> None:
    pages = _cn_engineering_syllabus_pages()
    syllabus_path = tmp_path / "CN syllabus.pdf"
    syllabus_path.write_bytes(b"%PDF-1.4")
    db_session.add(
        Course(id="CN", name="Computer Networks", structure_mode="mapped", outline_data=None)
    )
    db_session.add(
        Document(
            id=uuid.uuid4(),
            course_id="CN",
            filename="CN syllabus.pdf",
            doc_kind="syllabus",
            status="ready",
            file_path=str(syllabus_path),
        )
    )
    db_session.commit()

    mock_extract_pdf.return_value = type(
        "Extraction",
        (),
        {"pages": pages, "page_count": 2, "nonempty_pages": 2},
    )()

    result = rebuild_course_map_outline(db_session, "CN")
    assert result["rebuilt"] is True
    assert result["outline_summary"]["unit_count"] == 5

    outline = get_course_outline(db_session, "CN")
    assert outline is not None
    assert outline["outline_extraction_method"] == "syllabus_block"
    joined = " ".join(unit["title"].lower() for unit in outline["units"])
    assert "transport layer" in joined
    assert "application layer" in joined
