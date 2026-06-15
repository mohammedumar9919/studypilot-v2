"""FastAPI auth dependencies: Clerk JWT, dev bypass, workspace course access."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.clerk_jwt import verify_clerk_jwt
from app.config import settings
from app.database import get_session
from app.models import Course, Document, User, Workspace, WorkspaceMember
from app.services.workspaces import get_or_create_system_demo_workspace

DEV_BYPASS_CLERK_USER_ID = "dev-bypass"


@dataclass
class AuthContext:
    user: User | None
    workspace: Workspace


def get_or_create_dev_user(session: Session) -> User:
    user = session.scalar(select(User).where(User.clerk_user_id == DEV_BYPASS_CLERK_USER_ID))
    if user is not None:
        return user

    user = User(
        clerk_user_id=DEV_BYPASS_CLERK_USER_ID,
        email="dev@studypilot.local",
        display_name="Dev Bypass",
    )
    session.add(user)
    session.flush([user])
    return user


def get_current_user(session: Session, authorization: str | None) -> User:
    if settings.auth_disabled():
        return get_or_create_dev_user(session)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    try:
        claims = verify_clerk_jwt(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    user = session.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    if user is None:
        user = User(clerk_user_id=str(clerk_user_id))
        email = claims.get("email")
        if isinstance(email, str):
            user.email = email
        session.add(user)
        session.flush([user])
    return user


def get_active_workspace(session: Session, user: User) -> Workspace:
    stmt = (
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at)
        .limit(1)
    )
    workspace = session.scalar(stmt)
    if workspace is not None:
        return workspace

    workspace = Workspace(
        name="My Workspace",
        slug=f"user-{user.id}",
    )
    session.add(workspace)
    session.flush([workspace])
    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
    )
    session.flush()
    return workspace


def require_course_access(session: Session, course_id: str, workspace: Workspace) -> Course:
    course = session.get(Course, course_id)
    if course is None or course.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return course


def get_auth_context(
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    user = get_current_user(session, authorization)
    if settings.auth_disabled():
        workspace = get_or_create_system_demo_workspace(session)
    else:
        workspace = get_active_workspace(session, user)
    return AuthContext(user=user, workspace=workspace)


def require_course_access_dep(
    course_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Course:
    return require_course_access(session, course_id, auth.workspace)


def require_document_access_dep(
    document_id: uuid.UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    require_course_access(session, document.course_id, auth.workspace)
    return document
