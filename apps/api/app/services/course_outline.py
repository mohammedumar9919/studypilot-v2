"""Course outline API — read-only YAML fixture loader (no LLM)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Course
from app.services.pdf_extract import DocumentOutline, load_outline

_REPO_ROOT = Path(__file__).resolve().parents[4]

_OUTLINE_PATHS: dict[str, Path] = {
    "PPL": _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml",
}


@lru_cache(maxsize=8)
def _load_outline_file(path: str) -> DocumentOutline:
    return load_outline(Path(path))


def outline_path_for_course(course_id: str) -> Path | None:
    path = _OUTLINE_PATHS.get(course_id.upper())
    return path if path and path.is_file() else None


def serialize_course_outline(outline: DocumentOutline, course_id: str) -> dict[str, Any]:
    """JSON shape for GET /api/v1/courses/{course_id}/outline."""
    front_matter = None
    if outline.front_matter is not None:
        front_matter = {
            "title": outline.front_matter.title,
            "page_start": outline.front_matter.page_start,
            "page_end": outline.front_matter.page_end,
        }

    return {
        "course_id": course_id,
        "document": outline.document,
        "page_index_base": outline.page_index_base,
        "page_count": outline.page_count,
        "front_matter": front_matter,
        "units": [
            {
                "id": unit.id,
                "title": unit.title,
                "page_start": unit.page_start,
                "page_end": unit.page_end,
                "sections": [
                    {
                        "title": section.title,
                        "page_start": section.page_start,
                        "page_end": section.page_end,
                    }
                    for section in unit.sections
                ],
            }
            for unit in outline.units
        ],
    }


def get_course_outline(session: Session, course_id: str) -> dict[str, Any] | None:
    """
    Return outline JSON for a course, or None if course unknown / no outline fixture.

    v1: PPL loads eval/fixtures/ppl/ppl_outline.yaml (0-based page indices).
    """
    course = session.get(Course, course_id)
    if course is None:
        return None

    path = outline_path_for_course(course_id)
    if path is None:
        return None

    outline = _load_outline_file(str(path))
    return serialize_course_outline(outline, course_id)
