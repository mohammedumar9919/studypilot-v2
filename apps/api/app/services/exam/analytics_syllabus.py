"""Syllabus-primary exam analytics from parser unit/section hints (SP-061c)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models import ExamQuestion
from app.services.exam.reference_report import _extract_paper_code, _extract_year, is_subpart_row
from app.services.exam.subjects.registry import get_pack

PrimaryMode = str  # auto | syllabus | concepts
_VALID_PRIMARY = frozenset({"auto", "syllabus", "concepts"})


def _base_main_number(question_number: str | None) -> str | None:
    if not question_number:
        return None
    match = re.match(r"^(\d+)", question_number.strip())
    return match.group(1) if match else None


def _paper_row(paper_label: str | None) -> dict[str, Any]:
    code = _extract_paper_code(paper_label)
    year = _extract_year(paper_label)
    session_label = None
    if paper_label:
        parts = [part.strip() for part in paper_label.split("|")]
        if parts:
            session_label = parts[0]
    return {
        "session": session_label,
        "code": code,
        "year": year,
        "paper_label": paper_label,
        "format": "New" if code and ("/N" in code or code.isdigit()) else "Old" if code else None,
    }


def build_syllabus_primary_analytics(
    session: Session,
    course_id: str,
    questions: list[ExamQuestion],
) -> dict[str, Any]:
    pack = get_pack(course_id)
    subpart_rows = [question for question in questions if is_subpart_row(question.question_number)]
    rows = subpart_rows if subpart_rows else list(questions)

    unit_subparts: Counter[str] = Counter()
    unit_mains: Counter[str] = Counter()
    topic_subparts: Counter[str] = Counter()
    subtopic_subparts: Counter[str] = Counter()
    year_unit: dict[str, Counter[str]] = defaultdict(Counter)
    paper_stats: dict[str, dict[str, Any]] = {}

    main_keys: set[tuple[str | None, str | None]] = set()
    years: set[str] = set()

    for question in rows:
        unit, topic, subtopic = pack.classify_question(question, session=session)
        unit_subparts[unit] += 1
        topic_subparts[topic] += 1
        subtopic_subparts[subtopic] += 1

        year = _extract_year(question.paper_label)
        if year:
            years.add(year)
            year_unit[year][unit] += 1

        label = question.paper_label or "Unknown"
        stats = paper_stats.setdefault(
            label,
            {"paper_label": label, "main": 0, "sub": 0, **_paper_row(label)},
        )
        stats["sub"] += 1

        main_key = (label, _base_main_number(question.question_number))
        if main_key[1] and main_key not in main_keys:
            main_keys.add(main_key)
            stats["main"] += 1
            unit_mains[unit] += 1

    total_subparts = sum(unit_subparts.values()) or 1
    total_mains = len(main_keys)

    units = []
    for unit, count in unit_subparts.most_common():
        main_count = unit_mains.get(unit, 0)
        units.append(
            {
                "unit": unit,
                "subpart_count": count,
                "subpart_pct": round(count / total_subparts * 100.0, 1),
                "main_count": main_count,
                "main_pct": round(main_count / max(total_mains, 1) * 100.0, 1),
            }
        )

    top_topics = [
        {
            "name": name,
            "count": count,
            "pct": round(count / total_subparts * 100.0, 1),
        }
        for name, count in topic_subparts.most_common(10)
    ]
    top_subtopics = [
        {
            "name": name,
            "count": count,
            "pct": round(count / total_subparts * 100.0, 1),
        }
        for name, count in subtopic_subparts.most_common(12)
    ]

    papers_table = sorted(
        paper_stats.values(),
        key=lambda row: (row.get("year") or "", row.get("code") or row["paper_label"]),
    )

    return {
        "primary": "syllabus",
        "summary": {
            "paper_count": len(paper_stats),
            "main_question_count": total_mains,
            "subpart_count": total_subparts,
            "years": sorted(years),
        },
        "units": units,
        "top_topics": top_topics,
        "top_subtopics": top_subtopics,
        "papers_table": papers_table,
        "year_unit_matrix": {year: dict(counts) for year, counts in year_unit.items()},
    }


def apply_primary_analytics(
    payload: dict[str, Any],
    *,
    primary: str,
    include_flat: bool,
    syllabus_block: dict[str, Any] | None,
) -> dict[str, Any]:
    if primary not in _VALID_PRIMARY:
        raise ValueError(f"Unsupported primary: {primary}")

    result = dict(payload)
    if syllabus_block is None:
        return result

    result["syllabus_primary"] = syllabus_block
    if primary in {"syllabus", "auto"}:
        result["tier"] = max(int(result.get("tier") or 1), 2)
        if not include_flat:
            result["concepts"] = []
            result["pagination"] = {
                **result.get("pagination", {}),
                "total": 0,
                "flat_hidden": True,
            }
    return result
