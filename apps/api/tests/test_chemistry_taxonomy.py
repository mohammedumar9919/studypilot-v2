"""Tests for golden-aligned chemistry taxonomy."""

from __future__ import annotations

import uuid

from app.models import ExamQuestion
from app.services.exam.chemistry_taxonomy import (
    classify_chemistry_question,
    classify_chemistry_subtopic,
    map_chemistry_topic_keywords,
)


def _question(
    *,
    part: str,
    question_number: str,
    prompt_text: str,
    section_title: str | None = None,
    unit: str | None = None,
) -> ExamQuestion:
    return ExamQuestion(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        course_id="chemistry",
        page=1,
        paper_label="Sep/Oct 2023 | E-5616/N/BL | 2023",
        part=part,
        question_number=question_number,
        prompt_text=prompt_text,
        marks=2,
        unit=unit,
        section_title=section_title,
        extraction_method="regex",
    )


def test_map_chemistry_topic_keywords_prefers_specific_polymers() -> None:
    unit, topic = map_chemistry_topic_keywords("Explain conducting polymer polyacetylene.")
    assert unit == "Unit III"
    assert topic == "Conducting Polymers"


def test_part_a_positional_topic() -> None:
    question = _question(part="A", question_number="1a", prompt_text="Derive Nernst equation.")
    unit, topic, _subtopic = classify_chemistry_question(question)
    assert unit == "Unit I"
    assert topic == "Electrochemistry"


def test_part_c_q1_subtopic_rules() -> None:
    question = _question(
        part="C",
        question_number="1a",
        prompt_text="Explain EDTA method for hardness of water.",
    )
    _unit, _topic, subtopic = classify_chemistry_question(question)
    assert subtopic == "EDTA Hardness Method"


def test_part_c_q2_uses_in_unit_before_global() -> None:
    question = _question(
        part="C",
        question_number="2a",
        prompt_text="Derive Nernst equation for electrode potential.",
    )
    unit, topic, _subtopic = classify_chemistry_question(question)
    assert topic == "Electrochemistry"
    assert unit == "Unit I"


def test_part_c_q7_battery_main_stays_battery_without_global_hop() -> None:
    question = _question(
        part="C",
        question_number="7a",
        prompt_text="Explain preparation of silicone rubber.",
        section_title="Conducting Polymers",
    )
    unit, topic, _subtopic = classify_chemistry_question(question)
    assert topic == "Battery Chemistry"
    assert unit == "Unit I"


def test_composite_requires_strong_phrase_off_composite_main() -> None:
    question = _question(
        part="C",
        question_number="4a",
        prompt_text="Define composite.",
    )
    _unit, topic, _subtopic = classify_chemistry_question(question)
    assert topic != "Composites"


def test_q1_subtopic_prefers_section_title_over_keyword_bucket() -> None:
    question = _question(
        part="C",
        question_number="1a",
        prompt_text="Explain EDTA method for hardness of water.",
        section_title="Electrochemistry",
    )
    _unit, _topic, subtopic = classify_chemistry_question(question)
    assert subtopic == "Electrochemistry"


def test_part_c_q1_mixed_fallback_subtopic() -> None:
    question = _question(
        part="C",
        question_number="1b",
        prompt_text="Answer any two short definitions from the syllabus.",
    )
    _unit, _topic, subtopic = classify_chemistry_question(question)
    assert subtopic == "Mixed Part-A (New format Q1)"


def test_polymer_mislabel_uses_positional_unit() -> None:
    question = _question(
        part="B",
        question_number="14a",
        prompt_text="Explain proximate analysis of coal.",
        section_title="Specific Polymers",
        unit="Unit III",
    )
    unit, topic, _subtopic = classify_chemistry_question(question)
    assert unit == "Unit IV"
    assert topic == "Solid Fuels (Coal)"


def test_classify_chemistry_subtopic_nernst() -> None:
    subtopic = classify_chemistry_subtopic(
        "Derive Nernst equation for electrode potential.",
        part="B",
        main="11",
        topic="Electrochemistry",
    )
    assert subtopic == "Nernst Equation / EMF"
