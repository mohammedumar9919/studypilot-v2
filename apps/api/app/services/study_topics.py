"""CRUD for course study topics and document topic assignment."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Document, StudyTopic
from app.services.course_outline import outline_path_for_course

STUDY_PRESETS = frozenset({"study", "summary", "flashcards"})
ALLOWED_STRUCTURE_MODE_UPDATES = frozenset({"corpus", "organized"})


def serialize_study_topic(topic: StudyTopic) -> dict[str, Any]:
    return {
        "id": str(topic.id),
        "course_id": topic.course_id,
        "title": topic.title,
        "sort_order": topic.sort_order,
    }


def list_study_topics(session: Session, course_id: str) -> list[StudyTopic] | None:
    if session.get(Course, course_id) is None:
        return None
    stmt = (
        select(StudyTopic)
        .where(StudyTopic.course_id == course_id)
        .order_by(StudyTopic.sort_order, StudyTopic.title)
    )
    return list(session.scalars(stmt).all())


def create_study_topic(
    session: Session,
    course_id: str,
    *,
    title: str,
    sort_order: int = 0,
) -> StudyTopic:
    if session.get(Course, course_id) is None:
        raise ValueError(f"Course not found: {course_id}")
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")

    topic = StudyTopic(
        course_id=course_id,
        title=title,
        sort_order=sort_order,
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def update_study_topic(
    session: Session,
    course_id: str,
    topic_id: uuid.UUID,
    *,
    title: str | None = None,
    sort_order: int | None = None,
) -> StudyTopic:
    topic = session.get(StudyTopic, topic_id)
    if topic is None or topic.course_id != course_id:
        raise ValueError(f"Study topic not found: {topic_id}")

    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("title must not be empty")
        topic.title = cleaned
    if sort_order is not None:
        topic.sort_order = sort_order

    session.commit()
    session.refresh(topic)
    return topic


def delete_study_topic(session: Session, course_id: str, topic_id: uuid.UUID) -> None:
    topic = session.get(StudyTopic, topic_id)
    if topic is None or topic.course_id != course_id:
        raise ValueError(f"Study topic not found: {topic_id}")
    session.delete(topic)
    session.commit()


def assign_document_topic(
    session: Session,
    document_id: uuid.UUID,
    *,
    topic_id: uuid.UUID | None,
) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document not found: {document_id}")

    if topic_id is not None:
        topic = session.get(StudyTopic, topic_id)
        if topic is None or topic.course_id != document.course_id:
            raise ValueError(f"Study topic not found for document course: {topic_id}")

    document.topic_id = topic_id
    session.commit()
    session.refresh(document)
    return document


def is_mapped_fixture_course(course_id: str, course: Course | None = None) -> bool:
    """True only for fixture-backed courses (PPL YAML or outline_path_for_course)."""
    if course_id.upper() == "PPL":
        return True
    return outline_path_for_course(course_id) is not None


def validate_topic_ids(
    session: Session,
    *,
    course_id: str,
    topic_ids: list[str],
    preset: str,
) -> list[uuid.UUID]:
    """Parse and validate topic_ids for scoped study retrieval. Raises ValueError (400)."""
    if not topic_ids:
        raise ValueError("topic_ids must not be empty when provided")
    if preset not in STUDY_PRESETS:
        raise ValueError(f"topic_ids not allowed for preset {preset}")

    parsed: list[uuid.UUID] = []
    for raw_id in topic_ids:
        try:
            topic_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise ValueError(f"Invalid topic_ids UUID: {raw_id}") from exc

        topic = session.get(StudyTopic, topic_id)
        if topic is None or topic.course_id != course_id:
            raise ValueError(f"Study topic not found for course: {raw_id}")
        parsed.append(topic_id)

    return parsed


def update_structure_mode(session: Session, course_id: str, structure_mode: str) -> Course:
    """Set structure_mode; fixture courses (PPL / YAML) cannot demote to corpus."""
    if structure_mode not in ALLOWED_STRUCTURE_MODE_UPDATES:
        raise ValueError("structure_mode must be organized or corpus")

    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course not found: {course_id}")

    if structure_mode in ("corpus", "organized") and is_mapped_fixture_course(course_id, course):
        raise ValueError("Cannot demote mapped fixture course to corpus")

    course.structure_mode = structure_mode
    session.commit()
    session.refresh(course)
    return course


def bulk_create_study_topics(
    session: Session,
    course_id: str,
    *,
    titles: list[str],
) -> list[StudyTopic]:
    """Create topic stubs in order; promote corpus → organized when enabling Organized Study."""
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course not found: {course_id}")
    if not titles:
        raise ValueError("titles must not be empty")

    topics: list[StudyTopic] = []
    for index, raw_title in enumerate(titles):
        title = raw_title.strip()
        if not title:
            raise ValueError("title must not be empty")
        topic = StudyTopic(course_id=course_id, title=title, sort_order=index)
        session.add(topic)
        topics.append(topic)

    if course.structure_mode == "corpus":
        course.structure_mode = "organized"

    session.commit()
    for topic in topics:
        session.refresh(topic)
    return topics
