"""Tests for chemistry exam parse forensic audit (SP-062a)."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.models import Chunk, ChunkParent, Document, ExamQuestion
from app.services.exam.parse_audit import (
    audit_course,
    audit_pages,
    format_audit_markdown,
    match_golden_codes,
    normalize_paper_code,
    write_audit_report,
)
from app.services.exam.reference_report import load_golden_reference
from app.services.pdf_extract import PageText
from tests.conftest import add_test_course

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pyq"
GOLDEN_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json"
)


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _golden() -> dict:
    return load_golden_reference(GOLDEN_PATH)


def test_normalize_ocr_zero_to_letter_o() -> None:
    assert normalize_paper_code("E-5002/0/BL") == "E-5002/O/BL"
    assert normalize_paper_code("e 5002 / o / bl") == "E-5002/O/BL"


def test_match_codes_exact_fuzzy_missing() -> None:
    golden = ["E-5002/O/BL", "E-5616/N/BL", "15164"]
    assigned = match_golden_codes(["E-5002/O/BL", "E-5616/0/BL"], golden)
    assert assigned["E-5002/O/BL"]["match"] == "exact"
    assert assigned["E-5616/N/BL"]["match"] == "fuzzy"
    assert assigned["15164"]["match"] == "missing"


def test_match_does_not_collapse_bl_and_non_bl() -> None:
    golden = ["E-5002/O", "E-5002/O/BL"]
    assigned = match_golden_codes(["E-5002/O/BL"], golden)
    assert assigned["E-5002/O/BL"]["match"] == "exact"
    assert assigned["E-5002/O"]["match"] == "missing"


def test_page_unreadably_short_and_format_skip() -> None:
    golden = _golden()
    short = PageText(page=1, text="blank", char_count=5)
    cover = PageText(
        page=2,
        text=(
            "FACULTY OF ENGINEERING\nB.E. Degree Examination\n"
            "Subject : BS 204 CH — Engineering Chemistry\n"
            + ("examination instructions and rules for candidates. " * 8)
        ),
        char_count=400,
    )
    cover.char_count = len(cover.text)
    result = audit_pages(
        [short, cover],
        course_id="chemistry",
        filename="OU QUESTION PAPERS (1).pdf",
        golden=golden,
    )
    assert "unreadably_short" in result.pages[0].drop_reasons
    assert result.pages[0].detect_format == "skip"
    assert "format_skip" in result.pages[1].drop_reasons
    assert "no_code_no" in result.pages[1].drop_reasons
    assert "no_part_header" in result.pages[1].drop_reasons
    assert result.drop_counts["unreadably_short"] >= 1
    assert result.drop_counts["no_code_no"] >= 1
    assert result.drop_counts["no_part_header"] >= 1


def test_audit_fixture_codes_and_drafts() -> None:
    golden = _golden()
    old = _load("ou_chemistry_old_format.txt")
    new = _load("ou_chemistry_new_format.txt")
    pages = [
        PageText(page=1, text=old, char_count=len(old)),
        PageText(page=2, text=new, char_count=len(new)),
    ]
    result = audit_pages(
        pages,
        course_id="chemistry",
        filename="OU QUESTION PAPERS (1).pdf",
        golden=golden,
        db_question_rows=105,
    )
    by_code = {row.code: row for row in result.codes}
    assert by_code["E-5002/O/BL"].match == "exact"
    assert by_code["E-5616/N/BL"].match == "exact"
    assert by_code["E-5002/O/BL"].draft_rows > 0
    assert by_code["E-5616/N/BL"].draft_rows > 0
    assert "E-5002/O/BL" in result.papers_found
    assert "E-5616/N/BL" in result.papers_found
    assert "15164" in result.papers_missing
    assert result.replay_draft_rows > 0
    assert result.pages[0].detect_format == "part_ab"
    assert result.pages[1].detect_format == "compulsory_q1"

    markdown = format_audit_markdown(result)
    assert "papers_found" in markdown
    assert "papers_missing" in markdown
    assert "15164" in markdown
    assert "## Evidence" in markdown
    assert result.db_question_rows == 105


def test_write_report_and_course_from_chunks(db_session, tmp_path: Path) -> None:
    add_test_course(db_session, "chemistry", "Engineering Chemistry")
    old = _load("ou_chemistry_old_format.txt")
    garbled = old.replace("E-5002/O/BL", "E-5002/0/BL")
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    db_session.add(
        Document(
            id=doc_id,
            course_id="chemistry",
            filename="OU QUESTION PAPERS (1).pdf",
            doc_kind="past_paper",
            status="ready",
            page_count=1,
        )
    )
    db_session.add(
        ChunkParent(
            id=parent_id,
            document_id=doc_id,
            page_start=1,
            page_end=1,
            text=garbled,
        )
    )
    db_session.add(
        Chunk(
            id=uuid.uuid4(),
            parent_id=parent_id,
            document_id=doc_id,
            chunk_index=0,
            page=1,
            text=garbled,
            token_count=40,
        )
    )
    db_session.add(
        ExamQuestion(
            document_id=doc_id,
            course_id="chemistry",
            page=1,
            paper_label="Sep/Oct 2023 | E-5002/O/BL | 2023",
            question_number="11a",
            prompt_text="Explain electrochemical series.",
            extraction_method="regex",
        )
    )
    db_session.commit()

    result = audit_course(db_session, "chemistry", golden_path=GOLDEN_PATH)
    by_code = {row.code: row for row in result.codes}
    assert by_code["E-5002/O/BL"].match in {"exact", "fuzzy"}
    assert result.db_question_rows == 1
    assert "E-5002/O/BL" in result.papers_found
    assert len(result.papers_missing) >= 1

    report_path = tmp_path / "CHEMISTRY_PARSE_AUDIT.md"
    written = write_audit_report(result, report_path)
    text = written.read_text(encoding="utf-8")
    assert "papers_found" in text
    assert "papers_missing" in text
    assert "Measure-only report" in text
