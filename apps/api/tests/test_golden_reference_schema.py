"""Schema validation for per-subject exam golden reference JSON (SP-064c)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.exam.reference_report import (
    GOLDEN_SCHEMA_PATH,
    assert_golden_reference_schema,
    resolve_golden_path,
    validate_golden_reference_schema,
)

REPORTS = Path(__file__).resolve().parents[3] / "docs" / "reports"
CHEMISTRY_GOLDEN = REPORTS / "CHEMISTRY_GOLDEN_REFERENCE.json"
PPL_GOLDEN = REPORTS / "PPL_GOLDEN_REFERENCE.json"
TEMPLATE = REPORTS / "GOLDEN_REFERENCE_TEMPLATE.json"


def test_schema_file_exists() -> None:
    assert GOLDEN_SCHEMA_PATH.is_file()


def test_chemistry_golden_validates_against_schema() -> None:
    payload = json.loads(CHEMISTRY_GOLDEN.read_text(encoding="utf-8"))
    assert validate_golden_reference_schema(payload) == []
    assert_golden_reference_schema(payload)
    assert payload["meta"]["papers"] == 13
    assert payload["meta"]["subparts"] == 300
    assert sum(row["subpart_count"] for row in payload["units"]) == 300


def test_ppl_golden_validates_against_schema() -> None:
    payload = json.loads(PPL_GOLDEN.read_text(encoding="utf-8"))
    assert validate_golden_reference_schema(payload) == []
    assert_golden_reference_schema(payload)
    assert payload["meta"]["course_id"] == "PPL"
    assert payload["meta"]["papers"] == 1
    assert payload["meta"]["subparts"] == 25
    assert payload["meta"]["paper_count_source"] == "labels"
    assert payload["meta"]["confidence"] == "seed_confirmed"
    assert "estimates" in payload
    assert payload["estimates"]["total_questions_estimated_full_pdf"] == 50


def test_template_validates_against_schema() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert validate_golden_reference_schema(payload) == []


def test_schema_rejects_missing_meta() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    del payload["meta"]
    errors = validate_golden_reference_schema(payload)
    assert any("meta" in error for error in errors)


def test_resolve_golden_path_chemistry_and_ppl() -> None:
    chem = resolve_golden_path("chemistry")
    assert chem is not None
    assert chem.name == "CHEMISTRY_GOLDEN_REFERENCE.json"

    ppl = resolve_golden_path("PPL")
    assert ppl is not None
    assert ppl.name == "PPL_GOLDEN_REFERENCE.json"

    assert resolve_golden_path("UNKNOWN999") is None


def test_ppl_golden_unit_counts_sum_to_subparts() -> None:
    payload = json.loads(PPL_GOLDEN.read_text(encoding="utf-8"))
    assert sum(row["subpart_count"] for row in payload["units"]) == payload["meta"]["subparts"]


def test_ppl_estimates_marked_for_human_gate() -> None:
    payload = json.loads(PPL_GOLDEN.read_text(encoding="utf-8"))
    estimates = payload["estimates"]
    assert estimates["confidence"] == "estimated"
    assert estimates["total_questions_estimated_full_pdf"] == 50
