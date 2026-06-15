"""Tests for workspace schema and System Demo tenancy helpers."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Course, Workspace
from app.services.workspaces import (
    SYSTEM_DEMO_WORKSPACE_ID,
    SYSTEM_DEMO_WORKSPACE_NAME,
    SYSTEM_DEMO_WORKSPACE_SLUG,
    ensure_course_workspace,
    get_or_create_system_demo_workspace,
    list_workspace_courses,
)


def test_get_or_create_system_demo_workspace(db_session: Session) -> None:
    workspace = get_or_create_system_demo_workspace(db_session)
    db_session.commit()

    assert workspace.id == SYSTEM_DEMO_WORKSPACE_ID
    assert workspace.slug == SYSTEM_DEMO_WORKSPACE_SLUG
    assert workspace.name == SYSTEM_DEMO_WORKSPACE_NAME

    again = get_or_create_system_demo_workspace(db_session)
    assert again.id == workspace.id


def test_course_requires_workspace_id(db_session: Session) -> None:
    course = Course(id="NO_WS", name="No Workspace")
    db_session.add(course)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_ensure_course_workspace_assigns_system_demo(db_session: Session) -> None:
    course = Course(id="CHEM", name="Chemistry")
    db_session.add(course)

    ensure_course_workspace(db_session, course)
    db_session.commit()

    assert course.workspace_id == SYSTEM_DEMO_WORKSPACE_ID
    workspace = db_session.get(Workspace, SYSTEM_DEMO_WORKSPACE_ID)
    assert workspace is not None
    assert workspace.slug == SYSTEM_DEMO_WORKSPACE_SLUG


def test_ppl_course_in_system_demo_workspace(db_session: Session) -> None:
    workspace = get_or_create_system_demo_workspace(db_session)
    db_session.add(
        Course(
            id="PPL",
            name="Programming Languages",
            workspace_id=workspace.id,
            structure_mode="mapped",
        )
    )
    db_session.commit()

    courses = list_workspace_courses(db_session, SYSTEM_DEMO_WORKSPACE_ID)
    assert [course.id for course in courses] == ["PPL"]


def test_list_workspace_courses_scoped_by_workspace(db_session: Session) -> None:
    demo = get_or_create_system_demo_workspace(db_session)
    other_workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(
            id=other_workspace_id,
            name="Private",
            slug="private-test",
        )
    )
    db_session.add_all(
        [
            Course(id="PPL", name="PPL", workspace_id=demo.id),
            Course(id="CHEM", name="Chemistry", workspace_id=other_workspace_id),
        ]
    )
    db_session.commit()

    demo_courses = list_workspace_courses(db_session, demo.id)
    other_courses = list_workspace_courses(db_session, other_workspace_id)

    assert [course.id for course in demo_courses] == ["PPL"]
    assert [course.id for course in other_courses] == ["CHEM"]
