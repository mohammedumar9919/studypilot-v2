"""Course Map promotion — eligibility and corpus → mapped upgrade."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import Course
from app.services.course_outline import (
    build_outline_for_promotion,
    find_syllabus_document,
)
from app.services.study_topics import is_mapped_fixture_course

OutlineQuality = Literal["high", "medium", "low"]
OutlineSource = Literal["extracted", "uploaded", "auto_stub"]
StructureMode = Literal["corpus", "organized", "mapped"]


def outline_quality_for_course(course: Course) -> OutlineQuality | None:
    if not course.outline_data:
        return None
    quality = course.outline_data.get("outline_quality")
    if quality in ("high", "medium", "low"):
        return quality  # type: ignore[return-value]
    return None


def _stored_outline_source(course: Course) -> OutlineSource | None:
    if not course.outline_data:
        return None
    source = course.outline_data.get("outline_source")
    if source in ("extracted", "uploaded", "auto_stub"):
        return source  # type: ignore[return-value]
    return None


def _has_promotable_stored_outline(course: Course) -> bool:
    quality = outline_quality_for_course(course)
    source = _stored_outline_source(course)
    return quality in ("high", "medium") and source in ("extracted", "uploaded")


def _has_valid_extracted_outline(course: Course) -> bool:
    if not course.outline_data:
        return False
    source = course.outline_data.get("outline_source")
    quality = course.outline_data.get("outline_quality")
    units = course.outline_data.get("units") or []
    return source in ("extracted", "uploaded") and quality in ("high", "medium") and len(units) > 0


def _outline_preview_from_course(course: Course) -> dict[str, Any] | None:
    if not course.outline_data:
        return None
    units = course.outline_data.get("units") or []
    return {
        "outline_source": course.outline_data.get("outline_source"),
        "unit_count": len(units),
        "unit_titles": [str(unit.get("title", "")) for unit in units[:5]],
    }


def _outline_preview_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "outline_source": summary["outline_source"],
        "unit_count": summary["unit_count"],
        "unit_titles": list(summary["unit_titles"][:5]),
    }


def _outline_summary_from_build(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_count": summary["unit_count"],
        "unit_titles": summary["unit_titles"],
        "outline_quality": summary["outline_quality"],
        "outline_source": summary["outline_source"],
    }


def _dry_run_promotion_outline(session: Session, course_id: str) -> dict[str, Any] | None:
    try:
        return build_outline_for_promotion(session, course_id, dry_run=True)
    except ValueError:
        return None


def _ineligibility_reason(
    *,
    has_syllabus: bool,
    has_stored_outline: bool,
    dry_run_ok: bool,
    outline_quality: OutlineQuality | None,
) -> str:
    if not has_syllabus:
        return "no_syllabus_document"
    if has_stored_outline or dry_run_ok:
        return "not_eligible"
    if outline_quality is None:
        return "no_outline"
    return "outline_quality_not_high"


def get_course_map_eligibility(session: Session, course_id: str) -> dict[str, Any] | None:
    """Return eligibility payload, or None if the course is unknown."""
    course = session.get(Course, course_id)
    if course is None:
        return None

    structure_mode: StructureMode = course.structure_mode  # type: ignore[assignment]
    outline_quality = outline_quality_for_course(course)
    syllabus = find_syllabus_document(session, course_id)
    syllabus_filename = syllabus.filename if syllabus else None

    if is_mapped_fixture_course(course_id, course) or structure_mode == "mapped":
        return {
            "eligible": False,
            "outline_quality": outline_quality,
            "structure_mode": structure_mode,
            "reason": "already_mapped",
            "syllabus_filename": syllabus_filename,
            "outline_preview": _outline_preview_from_course(course),
        }

    has_syllabus = syllabus is not None
    has_stored_outline = _has_promotable_stored_outline(course)
    dry_run_summary = None
    if has_syllabus and not has_stored_outline:
        dry_run_summary = _dry_run_promotion_outline(session, course_id)
    dry_run_ok = dry_run_summary is not None

    eligible = structure_mode in ("corpus", "organized") and has_syllabus and (
        has_stored_outline or dry_run_ok
    )

    outline_preview = None
    if has_stored_outline:
        outline_preview = _outline_preview_from_course(course)
        outline_quality = outline_quality or outline_quality_for_course(course)
    elif dry_run_summary is not None:
        outline_preview = _outline_preview_from_summary(dry_run_summary)
        outline_quality = dry_run_summary["outline_quality"]

    reason = None
    if not eligible:
        reason = _ineligibility_reason(
            has_syllabus=has_syllabus,
            has_stored_outline=has_stored_outline,
            dry_run_ok=dry_run_ok,
            outline_quality=outline_quality,
        )

    return {
        "eligible": eligible,
        "outline_quality": outline_quality,
        "structure_mode": structure_mode,
        "reason": reason,
        "syllabus_filename": syllabus_filename,
        "outline_preview": outline_preview,
    }


def promotion_hint_for_course(session: Session, course_id: str, course: Course) -> str | None:
    """User-facing hint when corpus course can promote to Course Map."""
    if course.structure_mode != "corpus":
        return None
    eligibility = get_course_map_eligibility(session, course_id)
    if eligibility is None or not eligibility["eligible"]:
        return None
    return "Your course outline is ready. Promote to Course Map for unit sidebar and heatmap."


def _outline_summary_from_course(course: Course) -> dict[str, Any] | None:
    if not course.outline_data:
        return None
    units = course.outline_data.get("units") or []
    return {
        "unit_count": len(units),
        "unit_titles": [str(unit.get("title", "")) for unit in units],
        "outline_quality": course.outline_data.get("outline_quality"),
        "outline_source": course.outline_data.get("outline_source"),
    }


def rebuild_course_map_outline(session: Session, course_id: str) -> dict[str, Any]:
    """Re-extract syllabus TOC into outline_data without changing structure_mode."""
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course not found: {course_id}")
    if is_mapped_fixture_course(course_id, course):
        raise ValueError("Cannot rebuild outline for fixture-backed course")
    if find_syllabus_document(session, course_id) is None:
        raise ValueError("syllabus_document_not_found")

    outline_summary = build_outline_for_promotion(session, course_id, dry_run=False)
    session.commit()
    session.refresh(course)

    return {
        "course": course,
        "rebuilt": True,
        "outline_summary": _outline_summary_from_build(outline_summary),
    }


def promote_course_map(session: Session, course_id: str) -> dict[str, Any]:
    """Promote corpus/organized course to mapped using syllabus-driven outline extraction."""
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course not found: {course_id}")

    if is_mapped_fixture_course(course_id, course):
        return {
            "course": course,
            "promoted": False,
            "repaired": False,
            "outline_summary": _outline_summary_from_course(course),
        }

    if course.structure_mode == "mapped":
        if _has_valid_extracted_outline(course):
            return {
                "course": course,
                "promoted": False,
                "repaired": False,
                "outline_summary": _outline_summary_from_course(course),
            }
        if find_syllabus_document(session, course_id) is None:
            return {
                "course": course,
                "promoted": False,
                "repaired": False,
                "outline_summary": None,
            }
        outline_summary = build_outline_for_promotion(session, course_id, dry_run=False)
        session.commit()
        session.refresh(course)
        return {
            "course": course,
            "promoted": False,
            "repaired": True,
            "outline_summary": _outline_summary_from_build(outline_summary),
        }

    eligibility = get_course_map_eligibility(session, course_id)
    if eligibility is None or not eligibility["eligible"]:
        reason = (eligibility or {}).get("reason") or "not_eligible"
        raise ValueError(f"Course not eligible for Course Map promotion: {reason}")

    outline_summary = build_outline_for_promotion(session, course_id, dry_run=False)
    course.structure_mode = "mapped"
    session.commit()
    session.refresh(course)

    return {
        "course": course,
        "promoted": True,
        "repaired": False,
        "outline_summary": _outline_summary_from_build(outline_summary),
    }
