import os

os.environ.setdefault("STUDYPILOT_AUTH_DISABLED", "1")

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Course
from app.services.workspaces import SYSTEM_DEMO_WORKSPACE_ID

API_ROOT = Path(__file__).resolve().parents[1]


def add_test_course(session: Session, course_id: str, name: str, **kwargs) -> Course:
    workspace_id = kwargs.pop("workspace_id", SYSTEM_DEMO_WORKSPACE_ID)
    course = Course(id=course_id, name=name, workspace_id=workspace_id, **kwargs)
    session.add(course)
    return course


def _db_available() -> bool:
    try:
        engine = create_engine(settings.test_database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def migrated_db():
    if not _db_available():
        pytest.skip("Postgres test DB not available")
    env = os.environ.copy()
    env["DATABASE_URL"] = settings.test_database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"alembic migrate failed: {result.stderr}")


@pytest.fixture()
def db_session(migrated_db):
    engine = create_engine(settings.test_database_url)
    session = sessionmaker(bind=engine)()
    for table in (
        "chunk_embeddings",
        "chunks",
        "chunk_parents",
        "exam_questions",
        "document_part_links",
        "document_subtopic_links",
        "document_unit_links",
        "course_subtopics",
        "course_parts",
        "course_units",
        "documents",
        "study_topics",
        "courses",
        "workspace_members",
        "users",
        "workspaces",
    ):
        session.execute(text(f"TRUNCATE {table} CASCADE"))
    session.commit()
    from app.services.workspaces import get_or_create_system_demo_workspace

    get_or_create_system_demo_workspace(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()
