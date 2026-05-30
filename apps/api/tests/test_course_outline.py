"""Tests for GET /api/v1/courses/{course_id}/outline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Course
from app.services.course_outline import get_course_outline, serialize_course_outline
from app.services.pdf_extract import load_outline

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
OUTLINE_PATH = REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml"

client = TestClient(app)


def test_get_course_outline_ppl(db_session) -> None:
    db_session.add(Course(id="PPL", name="Programming Languages"))
    db_session.commit()

    result = get_course_outline(db_session, "PPL")
    assert result is not None
    assert result["course_id"] == "PPL"
    assert result["document"] == "PPL notes.pdf"
    assert result["page_index_base"] == 0
    assert len(result["units"]) == 5
    assert result["units"][0]["id"] == "1"
    assert result["units"][0]["title"] == "Preliminary Concepts"
    assert result["units"][0]["page_start"] == 3
    assert len(result["units"][0]["sections"]) == 2


def test_get_course_outline_unknown_course(db_session) -> None:
    assert get_course_outline(db_session, "UNKNOWN") is None


def test_get_course_outline_course_without_fixture(db_session) -> None:
    db_session.add(Course(id="CHEM", name="Chemistry"))
    db_session.commit()
    assert get_course_outline(db_session, "CHEM") is None


def test_api_course_outline_ppl(db_session) -> None:
    db_session.add(Course(id="PPL", name="Programming Languages"))
    db_session.commit()

    response = client.get("/api/v1/courses/PPL/outline")
    assert response.status_code == 200
    body = response.json()
    assert body["course_id"] == "PPL"
    assert len(body["units"]) == 5
    unit = body["units"][2]
    assert unit["id"] == "3"
    assert unit["title"] == "Subprograms and Blocks"
    assert unit["sections"][0]["page_start"] == 42


def test_api_course_outline_404() -> None:
    response = client.get("/api/v1/courses/UNKNOWN/outline")
    assert response.status_code == 404


def test_serialize_matches_yaml_fixture() -> None:
    outline = load_outline(OUTLINE_PATH)
    payload = serialize_course_outline(outline, "PPL")
    assert payload["page_count"] == 94
    assert payload["units"][-1]["id"] == "5"
    assert payload["units"][-1]["page_end"] == 93
