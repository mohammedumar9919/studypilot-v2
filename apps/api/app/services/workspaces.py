"""Workspace helpers and System Demo tenancy for dev/eval."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Workspace

SYSTEM_DEMO_WORKSPACE_ID = uuid.UUID("00000000-0000-4000-a000-000000000001")
SYSTEM_DEMO_WORKSPACE_SLUG = "system-demo"
SYSTEM_DEMO_WORKSPACE_NAME = "System Demo"

COURSE_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,62}$")


class CourseIdValidationError(ValueError):
    """Invalid course id format."""


class CourseConflictError(Exception):
    """Course id already exists in this or another workspace."""


def validate_course_id(course_id: str) -> str:
    normalized = course_id.strip()
    if not COURSE_ID_PATTERN.match(normalized):
        raise CourseIdValidationError(
            "Course id must match ^[A-Z0-9][A-Z0-9_-]{0,62}$ "
            "(uppercase letters, digits, underscore, hyphen; 1–63 chars)"
        )
    return normalized


def serialize_workspace_course(course: Course) -> dict[str, Any]:
    created_at = course.created_at
    if isinstance(created_at, datetime):
        created_at_value: str | None = created_at.isoformat()
    else:
        created_at_value = None
    return {
        "id": course.id,
        "name": course.name,
        "structure_mode": course.structure_mode,
        "created_at": created_at_value,
    }


def create_workspace_course(
    session: Session,
    workspace_id: uuid.UUID,
    course_id: str,
    name: str | None = None,
) -> Course:
    course_id = validate_course_id(course_id)
    existing = session.get(Course, course_id)
    if existing is not None:
        if existing.workspace_id == workspace_id:
            raise CourseConflictError(f"Course already exists in workspace: {course_id}")
        raise CourseConflictError(
            f"Course id already registered in another workspace: {course_id}"
        )

    course = Course(
        id=course_id,
        name=name or course_id,
        workspace_id=workspace_id,
    )
    session.add(course)
    session.flush([course])
    return course


def get_or_create_workspace_course(
    session: Session,
    workspace_id: uuid.UUID,
    course_id: str,
    name: str | None = None,
) -> Course:
    course_id = validate_course_id(course_id)
    existing = session.get(Course, course_id)
    if existing is not None:
        if existing.workspace_id != workspace_id:
            raise CourseConflictError(
                f"Course id already registered in another workspace: {course_id}"
            )
        return existing
    return create_workspace_course(session, workspace_id, course_id, name=name)


def get_or_create_system_demo_workspace(session: Session) -> Workspace:
    with session.no_autoflush:
        workspace = session.get(Workspace, SYSTEM_DEMO_WORKSPACE_ID)
        if workspace is not None:
            return workspace

        workspace = Workspace(
            id=SYSTEM_DEMO_WORKSPACE_ID,
            name=SYSTEM_DEMO_WORKSPACE_NAME,
            slug=SYSTEM_DEMO_WORKSPACE_SLUG,
        )
        session.add(workspace)
        session.flush([workspace])
        return workspace


def ensure_course_workspace(session: Session, course: Course) -> Course:
    if course.workspace_id is None:
        course.workspace_id = get_or_create_system_demo_workspace(session).id
        session.flush([course])
    return course


def list_workspace_courses(session: Session, workspace_id: uuid.UUID) -> list[Course]:
    stmt = (
        select(Course)
        .where(Course.workspace_id == workspace_id)
        .order_by(Course.id)
    )
    return list(session.scalars(stmt).all())
