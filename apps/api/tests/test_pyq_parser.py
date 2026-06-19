"""Tests for regex PYQ parser (SP-042a / SP-042c)."""

from __future__ import annotations

import uuid
from collections import Counter
from pathlib import Path

import fitz
import pytest
import yaml

from app.models import ExamQuestion
from app.services.exam.pyq_formats import detect_format
from app.services.exam.pyq_parser import (
    normalize_prompt,
    parse_exam_questions_from_pages,
    prompts_match,
)
from app.services.ingestion import ingest_document
from app.services.pdf_extract import PageText, extract_pdf, load_outline

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
PYQ_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pyq"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"
SEED_PATH = FIXTURES / "ppl_pyq_seed.yaml"
OUTLINE_PATH = FIXTURES / "ppl_outline.yaml"


def _load_pyq_fixture(name: str) -> str:
    return (PYQ_FIXTURES / name).read_text(encoding="utf-8").strip()


def _parse_fixture(name: str, page: int = 1) -> list:
    text = _load_pyq_fixture(name)
    outline = load_outline(OUTLINE_PATH)
    return parse_exam_questions_from_pages(
        pages=[PageText(page=page, text=text, char_count=len(text))],
        document_id=uuid.uuid4(),
        course_id="PPL",
        filename="fixture.pdf",
        outline=outline,
    )

JULY_2021_PAGE3_SYNTHETIC = """
FACULTY OF ENGINEERING
B.E. Examination, July 2021
Subject: Programming Languages

PART-A
Answer any five questions. (5x2 = 10 Marks)
1 What Programming Languages has dominated Artificial Intelligence over the past 40 years?
2 Describe the basic concept of Denotational Semantics.
3 Define a left recursive Grammar Rule.
4 What are the three fundamental features of Object Oriented Programming?
5 What three extensions are common to most EBNFs?
6 Compute the weakest precondition for each of the following statements.
7 Define Operator precedence and operator associativity
8 What is short circuit evaluation? Explain with an example?
9 Define functional form.
10 What are Horn Clauses? Write its general form and classify them?

PART-B
Answer any four questions. (4x15 = 60 Marks)
11 a) Explain the reasons for studying concepts of programming languages.
    b) Discuss Language evaluation criteria.
12 a) Prove the following grammar is ambiguous
    b) Define static, stack-dynamic, fixed heap-dynamic, and heap-dynamic arrays.
13 a) Discuss the different implementation models of parameter passing with examples.
    b) Explain templates in C++?
14 a) Explain concurrency in java using threads with an example.
    b) How is a user defined exception defined in Ada?
15 a) Write the following English conditional statements as Prolog headed Horn clauses.
    b) Explain how backtracking works in Prolog. Explain with an example.
16 a) Compare the multiple inheritance of C++ with that provided by interfaces in java.
    b) Write a program to find the number if prime or not in Python.
17 Write any two questions:
    a) Write notes on Attribute Grammar
    b) Deep Access Method
    c) Short notes on Functional Programming.
"""


def _page3_from_pdf() -> PageText | None:
    if not PAPERS_PDF.exists():
        return None
    doc = fitz.open(PAPERS_PDF)
    text = doc[2].get_text("text", sort=True) or ""
    doc.close()
    return PageText(page=3, text=text.strip(), char_count=len(text.strip()))


def test_synthetic_page3_part_counts() -> None:
    outline = load_outline(OUTLINE_PATH)
    page = PageText(page=3, text=JULY_2021_PAGE3_SYNTHETIC.strip(), char_count=500)
    drafts = parse_exam_questions_from_pages(
        pages=[page],
        document_id=uuid.uuid4(),
        course_id="PPL",
        filename="PPL previous papers.pdf",
        outline=outline,
    )
    part_a = [d for d in drafts if d.part == "A"]
    part_b = [d for d in drafts if d.part == "B"]
    assert len(part_a) >= 10
    assert len(part_b) >= 10


def test_seed_parity_page3() -> None:
    page = _page3_from_pdf()
    if page is None:
        pytest.skip("Missing PPL previous papers fixture")
    outline = load_outline(OUTLINE_PATH)
    drafts = parse_exam_questions_from_pages(
        pages=[page],
        document_id=uuid.uuid4(),
        course_id="PPL",
        filename="PPL previous papers.pdf",
        outline=outline,
    )
    seed = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    seed_questions = [q for q in seed["questions"] if int(q["page"]) == 3]

    misses: list[str] = []
    hits = 0
    for seed_row in seed_questions:
        if any(prompts_match(draft.prompt_text, seed_row["prompt"]) for draft in drafts):
            hits += 1
        else:
            misses.append(seed_row["prompt"])

    assert hits >= 20, f"Seed parity {hits}/{len(seed_questions)}; misses: {misses}"


def test_no_false_positives_on_junk_paragraph() -> None:
    junk = PageText(
        page=99,
        text="This is a random paragraph about photosynthesis and database normalization without exam structure.",
        char_count=120,
    )
    drafts = parse_exam_questions_from_pages(
        pages=[junk],
        document_id=uuid.uuid4(),
        course_id="PPL",
        filename="junk.pdf",
        outline=None,
    )
    assert drafts == []


def test_normalize_prompt_strips_punctuation() -> None:
    assert normalize_prompt("BNF, EBNF?") == "bnf ebnf"


def test_detect_format_profiles() -> None:
    assert detect_format(_load_pyq_fixture("compulsory_page1.txt")) == "compulsory_q1"
    assert detect_format(_load_pyq_fixture("dot_part_ab_page4.txt")) == "part_ab"
    assert detect_format(_load_pyq_fixture("unnumbered_part_a_page7.txt")) == "part_ab"
    cont_tail = "Code No. 3112/N\n2\n13 a) Explain briefly the criterion used to evaluate a programming language."
    assert detect_format(cont_tail) == "continuation"


def test_compulsory_page1_parses_q1_and_q2_7() -> None:
    drafts = _parse_fixture("compulsory_page1.txt", page=1)
    assert len(drafts) >= 18
    q1 = [d for d in drafts if d.question_number.startswith("1")]
    q2_7 = [d for d in drafts if d.question_number[0] in "234567"]
    assert len(q1) >= 7
    assert len(q2_7) >= 10
    assert all(d.part == "C" for d in drafts)


def test_dot_part_ab_page4_numbered_prompts() -> None:
    drafts = _parse_fixture("dot_part_ab_page4.txt", page=4)
    part_a = [d for d in drafts if d.part == "A"]
    part_b = [d for d in drafts if d.part == "B"]
    assert len(part_a) >= 8
    assert len(part_b) >= 8


def test_unnumbered_part_a_page7() -> None:
    drafts = _parse_fixture("unnumbered_part_a_page7.txt", page=7)
    part_a = [d for d in drafts if d.part == "A"]
    part_b = [d for d in drafts if d.part == "B"]
    assert len(part_a) >= 8
    assert len(part_b) >= 6


def test_continuation_merge_13_14() -> None:
    text = _load_pyq_fixture("continuation_13_14.txt")
    outline = load_outline(OUTLINE_PATH)
    page13 = PageText(page=13, text=text.split("Code No. 3112/N\n2\n")[0], char_count=500)
    page14 = PageText(
        page=14,
        text="Code No. 3112/N\n2\n" + text.split("Code No. 3112/N\n2\n", 1)[1],
        char_count=400,
    )
    drafts = parse_exam_questions_from_pages(
        pages=[page13, page14],
        document_id=uuid.uuid4(),
        course_id="PPL",
        filename="fixture.pdf",
        outline=outline,
    )
    assert len(drafts) >= 15
    pages = {d.page for d in drafts}
    assert 13 in pages


@pytest.mark.skipif(not PAPERS_PDF.exists(), reason="Missing PPL previous papers fixture")
def test_full_pdf_parse_count_with_ocr() -> None:
    result = extract_pdf(PAPERS_PDF)
    drafts = parse_exam_questions_from_pages(
        pages=result.pages,
        document_id=uuid.uuid4(),
        course_id="PPL",
        filename="PPL previous papers.pdf",
        outline=load_outline(OUTLINE_PATH),
    )
    pages_hit = len(Counter(d.page for d in drafts))
    assert len(drafts) >= 280, f"parsed={len(drafts)} pages_hit={pages_hit}"
    assert pages_hit >= 22, f"pages_hit={pages_hit}"


@pytest.mark.skipif(not PAPERS_PDF.exists(), reason="Missing PPL previous papers fixture")
def test_ingest_past_paper_persists_exam_questions(db_session) -> None:
    doc = ingest_document(
        db_session,
        file_path=PAPERS_PDF,
        course_id="PPL",
        doc_kind="past_paper",
    )
    assert doc.status == "ready"
    quality = doc.extraction_quality or {}
    assert quality.get("exam_parse_method") == "regex"
    assert int(quality.get("exam_questions_parsed", 0)) >= 280

    count = db_session.query(ExamQuestion).filter(ExamQuestion.document_id == doc.id).count()
    assert count >= 280
    assert count == int(quality["exam_questions_parsed"])


@pytest.mark.skipif(not PAPERS_PDF.exists(), reason="Missing PPL previous papers fixture")
def test_ingest_exam_questions_idempotent(db_session) -> None:
    doc1 = ingest_document(
        db_session,
        file_path=PAPERS_PDF,
        course_id="PPL",
        doc_kind="past_paper",
    )
    count1 = db_session.query(ExamQuestion).filter(ExamQuestion.document_id == doc1.id).count()
    doc2 = ingest_document(
        db_session,
        file_path=PAPERS_PDF,
        course_id="PPL",
        doc_kind="past_paper",
    )
    count2 = db_session.query(ExamQuestion).filter(ExamQuestion.document_id == doc2.id).count()
    assert doc1.id == doc2.id
    assert count1 == count2
    assert count1 >= 280
