"""Study layout API — mode + document sources for Flex Study sidebar (read-only)."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import Course, Document
from app.services.course_documents import list_course_documents, serialize_document
from app.services.course_map import promotion_hint_for_course
from app.services.course_outline import get_course_outline, outline_path_for_course
from app.services.study_topics import is_mapped_fixture_course, list_study_topics

StudyLayoutMode = Literal["corpus", "mapped"]
StructureMode = Literal["corpus", "organized", "mapped"]


def resolve_structure_mode(
    course_id: str,
    *,
    course: Course | None = None,
) -> StructureMode:
    """Use persisted structure_mode when present; else derive from fixture/outline rules."""
    if course is not None and course.structure_mode:
        return course.structure_mode  # type: ignore[return-value]

    if course_id.upper() == "PPL":
        return "mapped"
    if outline_path_for_course(course_id) is not None:
        return "mapped"
    if course is not None and course.outline_data:
        if course.outline_data.get("outline_quality") == "high":
            return "mapped"
    if course_id.lower() == "chemistry":
        return "mapped"
    return "corpus"


def resolve_study_layout_mode(
    course_id: str,
    *,
    course: Course | None = None,
) -> StudyLayoutMode:
    """Web-facing sidebar mode: mapped outline vs flat corpus (organized → corpus for 051a)."""
    structure = resolve_structure_mode(course_id, course=course)
    if structure == "mapped":
        return "mapped"
    return "corpus"


def build_sidebar_views(
    course_id: str,
    course: Course,
    *,
    structure_mode: StructureMode,
    documents: list[Document],
    topics: list,
    outline_available: bool,
) -> dict[str, bool]:
    """Flex Study sidebar tab visibility flags (SP-052.2)."""
    if is_mapped_fixture_course(course_id, course):
        return {
            "sources": False,
            "topics": False,
            "course_map": True,
        }

    has_docs = len(documents) > 0
    show_topics = structure_mode == "organized" or len(topics) > 0

    return {
        "sources": has_docs,
        "topics": show_topics,
        "course_map": outline_available,
    }


def get_study_layout(session: Session, course_id: str) -> dict[str, Any] | None:
    """Return study layout JSON for a course, or None if the course is unknown."""
    course = session.get(Course, course_id)
    if course is None:
        return None

    structure_mode = resolve_structure_mode(course_id, course=course)
    documents = list_course_documents(session, course_id)
    topics = list_study_topics(session, course_id) or []
    outline_available = get_course_outline(session, course_id) is not None
    sidebar_views = build_sidebar_views(
        course_id,
        course,
        structure_mode=structure_mode,
        documents=documents,
        topics=topics,
        outline_available=outline_available,
    )

    payload: dict[str, Any] = {
        "mode": resolve_study_layout_mode(course_id, course=course),
        "structure_mode": structure_mode,
        "course_id": course_id,
        "sources": [serialize_document(document) for document in documents],
        "sidebar_views": sidebar_views,
        "outline_available": outline_available,
    }
    hint = promotion_hint_for_course(session, course_id, course)
    if hint is not None:
        payload["promotion_hint"] = hint
    return payload
