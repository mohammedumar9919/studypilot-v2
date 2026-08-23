"""Tests for chemistry golden reference + validation CLI (SP-061a)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.exam.reference_report import (
    is_subpart_row,
    load_golden_reference,
    validate_against_golden,
)

GOLDEN_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json"
)


def test_golden_json_loads_and_meta_counts() -> None:
    golden = load_golden_reference(GOLDEN_PATH)
    meta = golden["meta"]
    assert meta["papers"] == 13
    assert meta["main_questions"] == 151
    assert meta["subparts"] == 300
    assert len(golden["papers"]) == 13
    assert sum(row["subpart_count"] for row in golden["units"]) == 300


def test_golden_json_schema_roundtrip() -> None:
    payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert "top_topics" in payload
    assert "year_unit_matrix" in payload
    assert payload["top_topics"][0]["name"] == "Electrochemistry"


def test_subpart_detection() -> None:
    assert is_subpart_row("11a")
    assert is_subpart_row("1b")
    assert is_subpart_row("7c")
    assert not is_subpart_row("11")
    assert not is_subpart_row(None)


def test_validate_empty_course(db_session) -> None:
    from tests.conftest import add_test_course

    add_test_course(db_session, "CHEMREF", "Chemistry Ref Test")
    db_session.commit()

    result = validate_against_golden(db_session, "CHEMREF", golden_path=GOLDEN_PATH)
    assert result["passed"] is False
    assert result["extended_passed"] is False
    assert result["app"]["subpart_count"] == 0
    assert any(row["name"] == "paper_code_count" for row in result["checks"])


def test_default_golden_path_resolves() -> None:
    from app.services.exam.reference_report import DEFAULT_GOLDEN_PATH

    golden = load_golden_reference(DEFAULT_GOLDEN_PATH)
    assert golden["meta"]["papers"] == 13
    assert DEFAULT_GOLDEN_PATH.name == "CHEMISTRY_GOLDEN_REFERENCE.json"


def test_validate_core_gate_ignores_extended_failures(db_session, monkeypatch) -> None:
    from tests.conftest import add_test_course

    add_test_course(db_session, "CHEMGATE", "Chem Gate")
    db_session.commit()

    def _metrics(_session, _course_id: str) -> dict:
        return {
            "question_rows": 302,
            "subpart_count": 302,
            "main_question_count": 150,
            "paper_label_count": 13,
            "paper_code_count": 13,
            "unit_subparts": {"Unit I": 0},
            "top_topics": [("Electrochemistry", 0)],
            "year_unit_matrix": {},
            "papers": [],
        }

    monkeypatch.setattr(
        "app.services.exam.reference_report.collect_app_metrics",
        _metrics,
    )
    result = validate_against_golden(db_session, "CHEMGATE", golden_path=GOLDEN_PATH)
    assert result["passed"] is True
    assert result["extended_passed"] is False
    assert any(row["name"] == "subpart_count" and row["ok"] for row in result["checks"])
    assert any(row["name"].startswith("unit_subparts:") and not row["ok"] for row in result["checks"])
