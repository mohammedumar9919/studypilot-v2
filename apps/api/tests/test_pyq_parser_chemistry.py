"""Tests for OU chemistry PYQ parser v2 (SP-061b)."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.services.exam.ou_chemistry import (
    detect_ou_paper_header,
    extract_ou_codes,
    is_ou_chemistry_source,
    map_chemistry_unit_section,
    normalize_ou_code,
    split_ou_bundle_text,
)
from app.services.exam.pyq_parser import parse_exam_questions_from_pages
from app.services.exam.reference_report import is_subpart_row
from app.services.pdf_extract import PageText

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pyq"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _parse(name: str) -> list:
    text = _load(name)
    return parse_exam_questions_from_pages(
        pages=[PageText(page=1, text=text, char_count=len(text))],
        document_id=uuid.uuid4(),
        course_id="chemistry",
        filename="OU QUESTION PAPERS (1).pdf",
    )


def test_is_ou_chemistry_source() -> None:
    assert is_ou_chemistry_source(course_id="chemistry", filename="paper.pdf")
    assert is_ou_chemistry_source(course_id="PPL", filename="OU QUESTION PAPERS (1).pdf")


def test_detect_paper_header_new_format() -> None:
    header = detect_ou_paper_header(_load("ou_chemistry_new_format.txt"))
    assert header.code == "E-5616/N/BL"
    assert header.paper_format == "New"
    assert header.paper_label is not None


def test_map_chemistry_unit_section_keywords() -> None:
    unit, section = map_chemistry_unit_section("Explain Nernst equation and EMF of a cell.")
    assert unit == "Unit I"
    assert section == "Electrochemistry"

    unit2, section2 = map_chemistry_unit_section("Explain EDTA method for hardness of water.")
    assert unit2 == "Unit II"
    assert section2 == "Water Chemistry"


def test_map_chemistry_by_position_part_b() -> None:
    from app.services.exam.ou_chemistry import map_chemistry_by_position

    unit, section = map_chemistry_by_position("B", "11a")
    assert unit == "Unit I"
    assert section == "Electrochemistry"

    unit2, section2 = map_chemistry_by_position("B", "14")
    assert unit2 == "Unit IV"


def test_old_format_maps_part_a_by_position() -> None:
    drafts = _parse("ou_chemistry_old_format.txt")
    units = {draft.unit for draft in drafts if draft.unit}
    assert "Unit I" in units
    assert "Unit IV" in units
    unmapped = [draft for draft in drafts if not draft.unit]
    assert len(unmapped) <= 2


def test_new_format_parses_subparts() -> None:
    drafts = _parse("ou_chemistry_new_format.txt")
    assert len(drafts) >= 14
    subparts = [draft for draft in drafts if is_subpart_row(draft.question_number)]
    assert len(subparts) >= 14
    assert any("Nernst" in draft.prompt_text or "electrochemical" in draft.prompt_text.lower() for draft in drafts)


def test_old_format_parses_part_b_subparts() -> None:
    drafts = _parse("ou_chemistry_old_format.txt")
    assert len(drafts) >= 20
    subparts = [draft for draft in drafts if is_subpart_row(draft.question_number)]
    assert len(subparts) >= 10
    assert any(draft.question_number == "11a" for draft in drafts)


def test_bundle_splitter_finds_multiple_headers() -> None:
    bundled = _load("ou_chemistry_old_format.txt") + "\n\n" + _load("ou_chemistry_new_format.txt")
    sections = split_ou_bundle_text(bundled)
    assert len(sections) >= 2


_SKIP_OLD_P1 = (
    "Code No: E-5002/O/BL/AICTE FACULTY OF ENGINEERING B.E. Examination, "
    "September / October 2023 Subject: Chemistry Time: 3 Hours Max. Marks: 70 "
    "PART -A Note: Answer all the questions. (10 x 2= 20 Marks) "
    "1. Write the cell reaction of the following cell notation: Ag/Ag+ || H+/H2/Pt. "
    "2. Differentiate primary and secondary battery. "
    "PART=B Note: Answer any five questions. (5 x 10 = 50 Marks) "
    "11. (a) Describe the construction of calomel electrode in detail with a neat diagram. "
    "(b) Explain the working of Lead-Acid storage battery as voltaic and as electrolytic cell."
)

_NO_CODE_NEW_P3 = (
    "Code No: E - 5616/N/BL/AICTE\n"
    "FACULTY OF ENGINEERING\n"
    "B.E. Examinations, September/October 2023\n"
    "Subject: Engineering Chemistry\n"
    "Note: (i) First question is compulsory and answer any four questions from the "
    "remaining six questions.\n"
    "1. (a) Differentiate between primary and secondary batteries.\n"
    "(b) The standard emf of Daniel cell is 1.1V. Calculate standard Gibbs energy.\n"
    "(c) What is alkalinity of water? Give the expression to estimate it.\n"
    "2. (a) Explain how pH of a solution is determined using Quinhydrone electrode.\n"
    "(b) What is a fuel cell? Give the construction of methanol-oxygen fuel cell.\n"
    "3. (a) Distinguish between zeolite softening and demineralization of water.\n"
    "(b) Discuss the mechanism of electrochemical corrosion.\n"
)


def test_normalize_ocr_zero_and_junk_codes() -> None:
    assert normalize_ou_code("D-2002/0") == "D-2002/O"
    assert normalize_ou_code("D-2014/O0/BL") == "D-2014/O/BL"
    assert normalize_ou_code("28000") is None
    assert normalize_ou_code("41000") is None
    assert extract_ou_codes("Calculate molecular weight of 28000 g/mol.") == []


def test_spaced_code_is_e_5616_n_bl() -> None:
    header = detect_ou_paper_header(_NO_CODE_NEW_P3)
    assert header.code == "E-5616/N/BL"
    assert header.paper_format == "New"


def test_skip_old_p1_yields_drafts_with_low_confidence() -> None:
    drafts = parse_exam_questions_from_pages(
        pages=[PageText(page=1, text=_SKIP_OLD_P1, char_count=len(_SKIP_OLD_P1))],
        document_id=uuid.uuid4(),
        course_id="chemistry",
        filename="OU QUESTION PAPERS.pdf",
    )
    assert len(drafts) > 0
    assert any(draft.paper_label and "E-5002/O/BL" in draft.paper_label for draft in drafts)
    assert all(draft.confidence < 0.7 for draft in drafts)


def test_no_code_new_p3_assigns_and_harvests() -> None:
    drafts = parse_exam_questions_from_pages(
        pages=[PageText(page=3, text=_NO_CODE_NEW_P3, char_count=len(_NO_CODE_NEW_P3))],
        document_id=uuid.uuid4(),
        course_id="chemistry",
        filename="OU QUESTION PAPERS.pdf",
    )
    assert len(drafts) > 0
    assert any(draft.paper_label and "E-5616/N/BL" in draft.paper_label for draft in drafts)
    assert any(draft.question_number.startswith("1") for draft in drafts)


def test_live_skip_e5002_obl_expands_midline_parts() -> None:
    drafts = _parse("ou_chemistry_e5002_obl_skip.txt")
    nums = {draft.question_number for draft in drafts}
    assert len(drafts) >= 8
    assert "11a" in nums
    assert any(num.startswith("1") for num in nums)
    assert any(is_subpart_row(draft.question_number) for draft in drafts)
    assert all(draft.confidence < 0.7 for draft in drafts)
    assert any(draft.paper_label and "E-5002/O/BL" in draft.paper_label for draft in drafts)


def test_live_new_e5807_expands_q1_and_romans() -> None:
    drafts = _parse("ou_chemistry_e5807_nbl_new.txt")
    nums = {draft.question_number for draft in drafts}
    assert "1a" in nums
    assert any(num.startswith("2") for num in nums)
    assert len([draft for draft in drafts if is_subpart_row(draft.question_number)]) >= 8
    assert any(draft.paper_label and "E-5807/N/BL" in draft.paper_label for draft in drafts)


def test_golden_gap_assigns_e_5616_between_neighbors() -> None:
    old_head = (
        "Code No: E-5002/O/BL/AICTE FACULTY OF ENGINEERING PART -A "
        "1. Define electrochemical cell. PART=B 11. (a) Explain Nernst equation."
    )
    unlabeled_new = (
        "FACULTY OF ENGINEERING\nB.E. Degree Examination BS 204 CH\n"
        "Note: First question is compulsory.\n"
        "1. (a) Differentiate primary and secondary batteries.\n"
        "2. (a) Explain EDTA method for hardness of water.\n"
    )
    next_old = _load("ou_chemistry_old_format.txt").replace("E-5002/O/BL", "E-5014/O/BL")
    bundled = old_head + "\n\n" + unlabeled_new + "\n\n" + next_old
    sections = split_ou_bundle_text(bundled)
    codes = [header.code for header, _text in sections]
    assert "E-5002/O/BL" in codes
    assert "E-5616/N/BL" in codes
    assert "E-5014/O/BL" in codes
