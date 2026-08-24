"""Tests for GenericPack structure-first taxonomy (SP-064b)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from app.models import Course, Document, ExamQuestion
from app.services.course_structure import confirm_course_structure
from app.services.exam.analytics import compute_exam_analytics
from app.services.exam.analytics_syllabus import build_syllabus_primary_analytics
from app.services.exam.subjects.generic import GenericPack
from app.services.exam.subjects.registry import get_pack
from tests.conftest import add_test_course


def _seed_ds_mapped(db_session) -> list[ExamQuestion]:
    add_test_course(db_session, "DS", "Data Science", structure_mode="mapped")
    confirm_course_structure(
        db_session,
        "DS",
        [
            {
                "title": "UNIT-I Data Science",
                "subtopics": ["Linear Algebra for data science", "Dimensionality reduction"],
            },
            {
                "title": "UNIT IV R Programming",
                "subtopics": ["Introduction to R Programming", "Data frames"],
            },
        ],
    )
    course = db_session.get(Course, "DS")
    assert course is not None
    course.structure_mode = "mapped"
    db_session.flush()
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="DS",
            filename="ds-pyq.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=2,
        )
    )
    questions = [
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="DS",
            page=1,
            paper_label="July 2023",
            question_number="1a",
            prompt_text="Explain linear algebra for data science with examples.",
            marks=10,
            extraction_method="regex",
        ),
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="DS",
            page=2,
            paper_label="July 2023",
            question_number="2a",
            prompt_text="Describe data frames in R programming.",
            marks=2,
            extraction_method="regex",
        ),
    ]
    db_session.add_all(questions)
    db_session.commit()
    return questions


def _seed_cn_mapped(db_session) -> list[ExamQuestion]:
    add_test_course(db_session, "CN", "Computer Networks", structure_mode="mapped")
    confirm_course_structure(
        db_session,
        "CN",
        [
            {
                "title": "Unit 1 Physical Layer",
                "parts": [
                    {"title": "Signals", "subtopics": ["Analog signals", "Digital signals"]},
                ],
            },
            {
                "title": "Unit 2 Transport",
                "subtopics": ["TCP", "UDP"],
            },
        ],
    )
    course = db_session.get(Course, "CN")
    assert course is not None
    course.structure_mode = "mapped"
    db_session.flush()
    doc_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="CN",
            filename="cn-pyq.pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=2,
        )
    )
    questions = [
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="CN",
            page=1,
            paper_label="May 2024",
            question_number="1a",
            prompt_text="Explain TCP three-way handshake.",
            marks=10,
            extraction_method="regex",
        ),
        ExamQuestion(
            id=uuid.uuid4(),
            document_id=doc_id,
            course_id="CN",
            page=2,
            paper_label="May 2024",
            question_number="2a",
            prompt_text="Explain analog signals and modulation techniques.",
            marks=5,
            extraction_method="regex",
        ),
    ]
    db_session.add_all(questions)
    db_session.commit()
    return questions


@patch("app.services.exam.analytics_structure.embed_texts")
def test_generic_pack_classifies_ds_structure_nodes(mock_embed, db_session) -> None:
    mock_embed.side_effect = lambda texts: [[0.0] for _ in texts]
    questions = _seed_ds_mapped(db_session)
    pack = get_pack("DS")
    assert isinstance(pack, GenericPack)

    unit, topic, subtopic = pack.classify_question(questions[0], session=db_session)
    assert unit == "UNIT-I Data Science"
    assert topic == "Linear Algebra for data science"
    assert subtopic == "Linear Algebra for data science"

    unit2, topic2, subtopic2 = pack.classify_question(questions[1], session=db_session)
    assert unit2 == "UNIT IV R Programming"
    assert "Data frames" in subtopic2


@patch("app.services.exam.analytics_structure.embed_texts")
def test_generic_pack_classifies_cn_structure_nodes(mock_embed, db_session) -> None:
    mock_embed.side_effect = lambda texts: [[0.0] for _ in texts]
    questions = _seed_cn_mapped(db_session)
    pack = get_pack("CN")

    unit, topic, subtopic = pack.classify_question(questions[0], session=db_session)
    assert unit == "Unit 2 Transport"
    assert topic == "TCP"
    assert subtopic == "TCP"

    unit2, topic2, subtopic2 = pack.classify_question(questions[1], session=db_session)
    assert unit2 == "Unit 1 Physical Layer"
    assert topic2 == "Signals"
    assert subtopic2 == "Analog signals"


@patch("app.services.exam.analytics_structure.embed_texts")
def test_syllabus_primary_ds_not_all_unmapped(mock_embed, db_session) -> None:
    mock_embed.side_effect = lambda texts: [[0.0] for _ in texts]
    questions = _seed_ds_mapped(db_session)
    block = build_syllabus_primary_analytics(db_session, "DS", questions)

    unit_names = {row["unit"] for row in block["units"]}
    topic_names = {row["name"] for row in block["top_topics"]}
    assert "Unmapped" not in unit_names
    assert "UNIT-I Data Science" in unit_names
    assert any("Linear Algebra" in name for name in topic_names)
    assert any("Data frames" in name for name in topic_names)


@patch("app.services.exam.analytics_structure.embed_texts")
def test_mapped_ds_auto_primary_uses_structure_labels(mock_embed, db_session) -> None:
    mock_embed.side_effect = lambda texts: [[0.0] for _ in texts]
    _seed_ds_mapped(db_session)
    payload = compute_exam_analytics(db_session, "DS", primary="auto", include_flat=False)
    assert payload["tier"] >= 2
    assert "syllabus_primary" in payload
    units = {row["unit"] for row in payload["syllabus_primary"]["units"]}
    assert "UNIT-I Data Science" in units
    assert "Unmapped" not in units


def test_parser_fallback_without_session(db_session) -> None:
    pack = GenericPack()
    question = ExamQuestion(
        course_id="X",
        prompt_text="Define polymorphism.",
        unit="Unit 3",
        section_title="OOP",
        extraction_method="regex",
    )
    unit, topic, subtopic = pack.classify_question(question)
    assert unit == "Unit 3"
    assert topic == "OOP"
    assert subtopic == "OOP"
