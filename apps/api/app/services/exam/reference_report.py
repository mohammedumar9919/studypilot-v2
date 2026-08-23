"""Compare course exam_question counts against CHEMISTRY_GOLDEN_REFERENCE.json (SP-061a)."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExamQuestion

_HERE = Path(__file__).resolve()


def _repo_root() -> Path:
    for parent in _HERE.parents:
        if (parent / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json").exists():
            return parent
    return _HERE.parents[5]


DEFAULT_GOLDEN_PATH = _repo_root() / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json"

_SUBPART_PATTERN = re.compile(r"^[0-9]+[a-g]$|^[0-9]+\.[a-g]$", re.IGNORECASE)
_MAIN_PATTERN = re.compile(r"^[0-9]+$")
_OU_CODE_PATTERN = re.compile(r"([ED]-\d{4}/[ON](?:/BL)?|\d{5})")


def load_golden_reference(path: Path | None = None) -> dict[str, Any]:
    golden_path = path or DEFAULT_GOLDEN_PATH
    with golden_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _base_question_number(question_number: str | None) -> str | None:
    if not question_number:
        return None
    normalized = question_number.strip().lower().replace(".", "")
    match = re.match(r"^(\d+)", normalized)
    return match.group(1) if match else None


def is_subpart_row(question_number: str | None) -> bool:
    if not question_number:
        return False
    normalized = question_number.strip().lower().replace(".", "")
    return bool(_SUBPART_PATTERN.match(normalized))


def is_main_row(question_number: str | None) -> bool:
    if not question_number:
        return False
    normalized = question_number.strip()
    if _MAIN_PATTERN.match(normalized):
        return True
    base = _base_question_number(normalized)
    return bool(base and _MAIN_PATTERN.match(base))


def _extract_paper_code(paper_label: str | None) -> str | None:
    if not paper_label:
        return None
    match = _OU_CODE_PATTERN.search(paper_label)
    return match.group(1) if match else None


def _extract_year(paper_label: str | None) -> str | None:
    if not paper_label:
        return None
    match = re.search(r"(20\d{2})", paper_label)
    return match.group(1) if match else None


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    cleaned = unit.strip().upper().replace("UNIT", "Unit")
    if cleaned.startswith("UNIT "):
        roman = cleaned.split()[-1]
        mapping = {"I": "Unit I", "II": "Unit II", "III": "Unit III", "IV": "Unit IV", "V": "Unit V"}
        if roman in mapping:
            return mapping[roman]
    if cleaned in {"Unit I", "Unit II", "Unit III", "Unit IV", "Unit V"}:
        return cleaned
    return unit.strip()


def collect_app_metrics(session: Session, course_id: str) -> dict[str, Any]:
    questions = list(session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == course_id)))
    subparts = [q for q in questions if is_subpart_row(q.question_number)]
    mains = [q for q in questions if is_subpart_row(q.question_number) is False]

    main_numbers = {
        (_extract_paper_code(q.paper_label), _base_question_number(q.question_number))
        for q in questions
        if _base_question_number(q.question_number)
    }
    main_numbers.discard((None, None))

    paper_labels = {q.paper_label for q in questions if q.paper_label}
    paper_codes = {_extract_paper_code(label) for label in paper_labels}
    paper_codes.discard(None)

    unit_subparts: Counter[str] = Counter()
    topic_subparts: Counter[str] = Counter()
    year_unit: dict[str, Counter[str]] = defaultdict(Counter)

    for question in subparts or questions:
        unit = _normalize_unit(question.unit)
        if unit:
            unit_subparts[unit] += 1
        if question.section_title:
            topic_subparts[question.section_title.strip()] += 1
        year = _extract_year(question.paper_label)
        if year and unit:
            year_unit[year][unit] += 1

    return {
        "question_rows": len(questions),
        "subpart_count": len(subparts) if subparts else len(questions),
        "main_question_count": len(main_numbers),
        "paper_label_count": len(paper_labels),
        "paper_code_count": len(paper_codes),
        "unit_subparts": dict(unit_subparts),
        "top_topics": topic_subparts.most_common(10),
        "year_unit_matrix": {year: dict(counts) for year, counts in year_unit.items()},
        "papers": sorted(paper_labels),
    }


def _pct_delta(app_value: float, golden_value: float) -> float:
    if golden_value == 0:
        return 0.0 if app_value == 0 else 100.0
    return abs(app_value - golden_value) / golden_value * 100.0


def validate_against_golden(
    session: Session,
    course_id: str,
    *,
    golden: dict[str, Any] | None = None,
    golden_path: Path | None = None,
) -> dict[str, Any]:
    reference = golden or load_golden_reference(golden_path)
    app = collect_app_metrics(session, course_id)
    meta = reference["meta"]
    tolerances = reference.get("tolerances", {})

    checks: list[dict[str, Any]] = []

    def add_check(name: str, expected: Any, actual: Any, *, ok: bool, detail: str = "") -> None:
        checks.append(
            {
                "name": name,
                "expected": expected,
                "actual": actual,
                "ok": ok,
                "detail": detail,
            }
        )

    add_check(
        "paper_code_count",
        meta["papers"],
        app["paper_code_count"],
        ok=app["paper_code_count"] == meta["papers"],
    )
    add_check(
        "main_question_count",
        meta["main_questions"],
        app["main_question_count"],
        ok=tolerances.get("main_questions_min", 145)
        <= app["main_question_count"]
        <= tolerances.get("main_questions_max", 155),
    )
    add_check(
        "subpart_count",
        meta["subparts"],
        app["subpart_count"],
        ok=tolerances.get("subpart_count_min", 290)
        <= app["subpart_count"]
        <= tolerances.get("subpart_count_max", 310),
    )

    golden_units = {row["unit"]: row["subpart_count"] for row in reference["units"]}
    unit_delta_max = tolerances.get("unit_subpart_delta_max", 5)
    for unit, expected in golden_units.items():
        actual = app["unit_subparts"].get(unit, 0)
        add_check(
            f"unit_subparts:{unit}",
            expected,
            actual,
            ok=abs(actual - expected) <= unit_delta_max,
            detail=f"delta={actual - expected}",
        )

    golden_top = reference.get("top_topics", [])[:10]
    rel_tol = tolerances.get("top_topic_relative_pct", 15.0)
    app_topic_map = dict(app["top_topics"])
    for row in golden_top:
        actual = app_topic_map.get(row["name"], 0)
        add_check(
            f"top_topic:{row['name']}",
            row["count"],
            actual,
            ok=_pct_delta(actual, row["count"]) <= rel_tol,
            detail=f"rel_delta={_pct_delta(actual, row['count']):.1f}%",
        )

    passed = all(
        row["ok"]
        for row in checks
        if row["name"] in {"paper_code_count", "main_question_count", "subpart_count"}
    )
    extended_passed = all(row["ok"] for row in checks)
    return {
        "course_id": course_id,
        "passed": passed,
        "extended_passed": extended_passed,
        "app": app,
        "golden_meta": meta,
        "checks": checks,
    }


def format_validation_report(result: dict[str, Any]) -> str:
    core_names = {"paper_code_count", "main_question_count", "subpart_count"}
    verdict = "PASS" if result["passed"] else "FAIL"
    extended = result.get("extended_passed", result["passed"])
    lines = [
        f"Exam reference validation — course={result['course_id']} — {verdict}",
        f"Core gate (papers / mains / subs): {'PASS' if result['passed'] else 'FAIL'}",
        f"Extended (units / top topics): {'PASS' if extended else 'FAIL'}",
        "",
        f"{'Check':<32} {'Expected':>10} {'Actual':>10} {'OK':>4}  Detail",
        "-" * 72,
    ]
    for row in result["checks"]:
        gate = "core" if row["name"] in core_names else "ext"
        lines.append(
            f"{row['name']:<32} {str(row['expected']):>10} {str(row['actual']):>10} "
            f"{'yes' if row['ok'] else 'no':>4}  [{gate}] {row.get('detail', '')}"
        )
    lines.append("")
    lines.append(
        f"App summary: papers={result['app']['paper_code_count']} "
        f"mains={result['app']['main_question_count']} "
        f"subparts={result['app']['subpart_count']} rows={result['app']['question_rows']}"
    )
    return "\n".join(lines)
