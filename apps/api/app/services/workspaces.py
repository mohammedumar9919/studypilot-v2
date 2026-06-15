"""Workspace helpers and System Demo tenancy for dev/eval."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Workspace

SYSTEM_DEMO_WORKSPACE_ID = uuid.UUID("00000000-0000-4000-a000-000000000001")
SYSTEM_DEMO_WORKSPACE_SLUG = "system-demo"
SYSTEM_DEMO_WORKSPACE_NAME = "System Demo"


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
