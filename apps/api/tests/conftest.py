import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

API_ROOT = Path(__file__).resolve().parents[1]


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
        "document_subtopic_links",
        "document_unit_links",
        "course_subtopics",
        "course_units",
        "documents",
        "study_topics",
        "courses",
    ):
        session.execute(text(f"TRUNCATE {table} CASCADE"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
