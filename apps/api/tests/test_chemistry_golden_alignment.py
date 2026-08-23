"""Integration: syllabus-primary analytics vs CHEMISTRY_GOLDEN_REFERENCE.json (SP-063b)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import ExamQuestion
from app.services.exam.analytics_syllabus import build_syllabus_primary_analytics
from app.services.exam.reference_report import load_golden_reference, validate_against_golden

GOLDEN_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json"
)


@pytest.fixture
def golden_reference() -> dict:
    return load_golden_reference(GOLDEN_PATH)


def test_build_syllabus_primary_analytics_matches_golden_units(db_session, golden_reference) -> None:
    questions = list(
        db_session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == "chemistry"))
    )
    if not questions:
        pytest.skip("chemistry exam_questions corpus not loaded")

    block = build_syllabus_primary_analytics(db_session, "chemistry", questions)
    golden_units = {row["unit"]: row["subpart_count"] for row in golden_reference["units"]}
    live_units = {row["unit"]: row["subpart_count"] for row in block["units"]}
    delta_max = golden_reference["tolerances"]["unit_subpart_delta_max"]

    for unit, expected in golden_units.items():
        actual = live_units.get(unit, 0)
        assert abs(actual - expected) <= delta_max, f"{unit}: live={actual} golden={expected}"


def test_build_syllabus_primary_top_topics_within_relative_tolerance(
    db_session, golden_reference
) -> None:
    questions = list(
        db_session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == "chemistry"))
    )
    if not questions:
        pytest.skip("chemistry exam_questions corpus not loaded")

    block = build_syllabus_primary_analytics(db_session, "chemistry", questions)
    live_map = {row["name"]: row["count"] for row in block["top_topics"]}
    rel_tol = golden_reference["tolerances"]["top_topic_relative_pct"]

    for row in golden_reference["top_topics"][:10]:
        expected = row["count"]
        actual = live_map.get(row["name"], 0)
        if expected == 0:
            continue
        rel_delta = abs(actual - expected) / expected * 100.0
        assert rel_delta <= rel_tol, f"{row['name']}: live={actual} golden={expected} ({rel_delta:.1f}%)"


def test_validate_against_golden_core_gate(db_session, golden_reference) -> None:
    questions = list(
        db_session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == "chemistry"))
    )
    if not questions:
        pytest.skip("chemistry exam_questions corpus not loaded")

    result = validate_against_golden(db_session, "chemistry", golden=golden_reference)
    assert result["passed"] is True
