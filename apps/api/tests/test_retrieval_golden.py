"""Golden-set retrieval tests (hybrid + gate on live or ingested DB)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.rag.pipeline import run_study_question
from app.services.rag.retrieve import _rrf_fuse, infer_unit_hints, replay_golden_set, section_page_hints, unit_page_range

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_PATH = REPO_ROOT / "eval" / "golden_set.jsonl"
FIXTURES = REPO_ROOT / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"


def _load_golden() -> list[dict]:
    rows: list[dict] = []
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_section_page_hints_narrow_functional_section() -> None:
    hints = section_page_hints("What is referential transparency in functional programming languages?")
    assert hints
    start, end = hints[0]
    assert start == 85 and end == 88
    assert 86 in range(start, end + 1)


def test_section_page_hints_paradigm_cluster() -> None:
    hints = section_page_hints("Explain programming paradigms: imperative, functional, logic")
    assert hints
    assert (3, 9) in hints


def test_page_phrase_anchors_query_first() -> None:
    from app.services.rag.retrieve import _page_phrase_anchors_for_query

    anchors = _page_phrase_anchors_for_query(
        "Explain programming paradigms: imperative, functional, logic"
    )
    assert anchors[0] == "programming paradigms"


def test_section_page_hints_remaining_misses() -> None:
    eval_hints = section_page_hints(
        "What are the language evaluation criteria for programming languages?"
    )
    assert (4, 6) in eval_hints
    comp_hints = section_page_hints(
        "What is compilation versus interpretation in language implementation?"
    )
    assert (6, 8) in comp_hints
    oop_hints = section_page_hints(
        "What are the three fundamental features of object-oriented programming?"
    )
    assert (52, 54) in oop_hints


def test_rerank_scores_all_candidates_not_only_top_raw() -> None:
    import uuid
    from unittest.mock import patch

    from app.services.rag.rerank import rerank_chunks
    from app.services.rag.retrieve import RetrievedChunk

    def _chunk(page: int, text: str) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            filename="PPL notes.pdf",
            doc_kind="notes",
            page=page,
            text=text,
            parent_text=text,
            unit="1",
            section_title="Preliminary Concepts",
            toc_path="Unit 1 > Preliminary Concepts",
        )

    q = "What are the language evaluation criteria for programming languages?"
    chunks = [
        _chunk(72, "object-oriented programming languages"),
        _chunk(5, "language evaluation criteria include readability and cost"),
        _chunk(33, "operator precedence in expressions"),
    ]
    raw_scores = [5.0, 0.5, 4.0]

    with patch("app.services.rag.rerank.get_reranker") as mock_reranker:
        mock_reranker.return_value.rerank_pairs.return_value = raw_scores
        ranked = rerank_chunks(q, chunks, top_k=2)

    assert ranked[0].page in {4, 5, 6}


def test_ppl_002_evaluation_criteria_helpers() -> None:
    from app.services.rag.retrieve import _to_tsquery_and, focus_terms

    q = "What are the language evaluation criteria for programming languages?"
    assert (4, 6) in section_page_hints(q)
    terms = focus_terms(q)
    assert "evaluation criteria" in terms
    assert _to_tsquery_and(["evaluation", "criteria"]) == "evaluation & criteria"


def test_infer_unit_hints_from_golden_patterns() -> None:
    assert infer_unit_hints("Explain programming paradigms: imperative, functional, logic")[0] == "1"
    assert infer_unit_hints("Write notes on functional programming.")[0] == "5"
    assert infer_unit_hints("What is short-circuit evaluation? Explain with an example.")[0] == "2"
    assert infer_unit_hints(
        "What are the language evaluation criteria for programming languages?"
    )[0] == "1"
    assert infer_unit_hints(
        "What programming language has dominated artificial intelligence over decades"
    )[0] == "5"


def test_unit_page_range_from_outline() -> None:
    unit1 = unit_page_range("1")
    assert unit1 is not None
    assert unit1[0] <= 8 <= unit1[1]
    unit5 = unit_page_range("5")
    assert unit5 is not None
    assert unit5[0] <= 86 <= unit5[1]


def test_rrf_fuse_merges_rankings() -> None:
    import uuid

    id_a, id_b, id_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    vector_hits = [
        {"chunk_id": id_a, "page": 1, "text": "a", "filename": "f", "doc_kind": "notes",
         "document_id": uuid.uuid4(), "parent_id": None, "vector_score": 0.9},
        {"chunk_id": id_b, "page": 2, "text": "b", "filename": "f", "doc_kind": "notes",
         "document_id": uuid.uuid4(), "parent_id": None, "vector_score": 0.8},
    ]
    bm25_hits = [
        {"chunk_id": id_c, "page": 3, "text": "c", "filename": "f", "doc_kind": "notes",
         "document_id": uuid.uuid4(), "parent_id": None, "bm25_score": 0.7},
        {"chunk_id": id_a, "page": 1, "text": "a", "filename": "f", "doc_kind": "notes",
         "document_id": uuid.uuid4(), "parent_id": None, "bm25_score": 0.6},
    ]
    fused = _rrf_fuse(vector_hits, bm25_hits, k=60, vector_weight=1.0, bm25_weight=1.0, top_n=3)
    ids = [row["chunk_id"] for row in fused]
    assert id_a in ids
    assert len(fused) == 3


def test_replay_golden_set_schema() -> None:
    golden = _load_golden()[:2]
    from app.services.rag.pipeline import StudyQuestionResult
    from app.services.rag.retrieve import RetrievedChunk
    import uuid

    def _fake_run(session, course_id, question, preset="study"):
        return StudyQuestionResult(
            status="ok",
            chunks=[
                RetrievedChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    filename="PPL notes.pdf",
                    doc_kind="notes",
                    page=4,
                    text="x",
                    parent_text=None,
                    rerank_score=0.9,
                )
            ],
            rerank_scores=[0.9],
        )

    import app.services.rag.pipeline as pipeline_mod

    original = pipeline_mod.run_study_question
    pipeline_mod.run_study_question = _fake_run
    try:
        results = replay_golden_set(golden)
    finally:
        pipeline_mod.run_study_question = original
    assert len(results) == 2
    for row in results:
        assert "id" in row
        assert row["status"] in ("ok", "not_in_materials")
        assert "retrieved_pages" in row


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_study_retrieval_excludes_past_paper_bnf(db_session) -> None:
    from app.services.ingestion import ingest_document

    ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    if PAPERS_PDF.exists():
        ingest_document(db_session, file_path=PAPERS_PDF, course_id="PPL", doc_kind="past_paper")
    db_session.commit()

    outcome = run_study_question(
        db_session,
        course_id="PPL",
        question="What is BNF and how do you describe a list using recursion in BNF?",
        preset="study",
    )
    if outcome.status == "ok":
        assert all(c.doc_kind != "past_paper" for c in outcome.chunks)


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_study_retrieval_excludes_past_paper_lexeme(db_session) -> None:
    from app.services.ingestion import ingest_document

    papers_pdf = FIXTURES / "PPL previous papers.pdf"
    if not papers_pdf.exists():
        pytest.skip("Missing past papers fixture")

    ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    ingest_document(db_session, file_path=papers_pdf, course_id="PPL", doc_kind="past_paper")
    db_session.commit()

    outcome = run_study_question(
        db_session,
        course_id="PPL",
        question="Define lexeme and token with examples.",
        preset="study",
    )
    if outcome.status == "ok":
        assert all(c.doc_kind != "past_paper" for c in outcome.chunks)


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_study_retrieval_lexeme_question(db_session) -> None:
    from app.services.ingestion import ingest_document

    ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    db_session.commit()

    outcome = run_study_question(
        db_session,
        course_id="PPL",
        question="Define lexeme and token with examples.",
        preset="study",
    )
    assert outcome.status in ("ok", "not_in_materials")
    if outcome.status == "ok":
        assert outcome.chunks
        assert all(c.doc_kind in ("notes", "textbook", "syllabus") for c in outcome.chunks)
        pages = {c.page for c in outcome.chunks}
        assert any(p in {10, 11, 12} for p in pages)


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_ooc_question_refused(db_session) -> None:
    from app.services.ingestion import ingest_document

    ingest_document(db_session, file_path=NOTES_PDF, course_id="PPL", doc_kind="notes")
    db_session.commit()

    outcome = run_study_question(
        db_session,
        course_id="PPL",
        question="Explain the mechanism of photosynthesis in plants.",
        preset="study",
    )
    assert outcome.status == "not_in_materials"
    assert outcome.chunks == []
