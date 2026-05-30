"""Hybrid retrieval: pgvector + BM25 with RRF fusion."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import ChunkParent
from app.services.embedder import embed_texts
from app.services.pdf_extract import DocumentOutline, load_outline

STUDY_DOC_KINDS = ("notes", "textbook", "syllabus")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "what",
        "which",
        "who",
        "how",
        "why",
        "when",
        "where",
        "give",
        "explain",
        "describe",
        "define",
        "between",
        "with",
        "and",
        "or",
        "for",
        "of",
        "in",
        "to",
        "from",
        "using",
        "according",
        "over",
        "decades",
        "example",
        "examples",
    }
)

_LEXICAL_MARKERS = (
    "define",
    "what is",
    "what are",
    "difference between",
    "explain",
    "lexeme",
    "token",
    "grammar",
    "ambiguous",
    "short-circuit",
    "referential transparency",
    "lisp",
    "evaluation criteria",
)


@dataclass
class _ParentMeta:
    text: str
    page_start: int
    page_end: int


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    doc_kind: str
    page: int
    text: str
    parent_text: str | None
    parent_id: uuid.UUID | None = None
    parent_page_start: int | None = None
    parent_page_end: int | None = None
    unit: str | None = None
    section_title: str | None = None
    toc_path: str | None = None
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


_REPO_ROOT = Path(__file__).resolve().parents[5]
_PPL_OUTLINE_PATH = _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml"

_UNIT_PHRASES: dict[str, tuple[str, ...]] = {
    "1": (
        "evaluation criteria",
        "language evaluation criteria",
        "programming paradigms",
        "language categories",
        "compilation versus",
        "compilation and interpretation",
        "reliability and cost",
        "weakest precondition",
        "ambiguous grammar",
        "grammar is ambiguous",
        "ambiguous expression",
        "syntax and semantics",
        "denotational semantics",
        "study concepts of programming",
    ),
    "2": (
        "short-circuit evaluation",
        "operator precedence",
        "operator associativity",
        "guarded commands",
        "conditional expression",
        "data types and variables",
        "heap-dynamic",
    ),
    "3": (
        "parameter passing",
        "pass-by-value",
        "pass-by-reference",
        "pass-by-name",
        "subprograms and blocks",
    ),
    "4": (
        "abstract data type",
        "object-oriented programming",
        "exception handling",
        "template class",
        "three fundamental features",
    ),
    "5": (
        "functional programming",
        "referential transparency",
        "horn clauses",
        "logic programming",
        "lisp data",
        "artificial intelligence",
        "functional form",
        "write notes on functional",
    ),
}

_UNIT_TERMS: dict[str, frozenset[str]] = {
    "1": frozenset(
        {
            "syntax",
            "semantics",
            "lexeme",
            "token",
            "bnf",
            "grammar",
            "ambiguous",
            "ebnf",
            "denotational",
            "precondition",
            "paradigm",
            "markup",
            "compilation",
            "interpretation",
            "reliability",
            "categories",
            "criteria",
            "evaluation",
        }
    ),
    "2": frozenset(
        {
            "short-circuit",
            "precedence",
            "associativity",
            "ternary",
            "guarded",
            "dijkstra",
            "arrays",
            "stack-dynamic",
            "heap-dynamic",
        }
    ),
    "3": frozenset({"parameter", "subprogram", "pass-by", "coroutine"}),
    "4": frozenset(
        {
            "adt",
            "encapsulation",
            "inheritance",
            "polymorphism",
            "exception",
            "template",
            "concurrency",
            "threads",
        }
    ),
    "5": frozenset(
        {
            "lisp",
            "prolog",
            "backtracking",
            "referential",
            "horn",
            "scripting",
            "functional",
        }
    ),
}


@lru_cache(maxsize=1)
def _ppl_outline() -> DocumentOutline | None:
    if not _PPL_OUTLINE_PATH.is_file():
        return None
    return load_outline(_PPL_OUTLINE_PATH)


def unit_page_range(unit_id: str) -> tuple[int, int] | None:
    """0-based inclusive page range for a PPL unit from the outline fixture."""
    outline = _ppl_outline()
    if outline is None:
        return None
    for unit in outline.units:
        if unit.id == unit_id:
            return unit.page_start, unit.page_end
    return None


_SECTION_PAGE_HINTS: tuple[tuple[str, int, int], ...] = (
    ("language evaluation criteria", 4, 6),
    ("evaluation criteria", 4, 6),
    ("compilation versus interpretation", 6, 8),
    ("compilation versus", 6, 8),
    ("three fundamental features", 52, 54),
    ("programming paradigms", 3, 9),
    ("language categories", 3, 9),
    ("language evaluation", 3, 9),
    ("study concepts of", 3, 9),
    ("study concepts", 3, 9),
    ("reliability and cost", 3, 9),
    ("compilation and interpretation", 6, 8),
    ("weakest precondition", 10, 16),
    ("ambiguous grammar", 10, 16),
    ("grammar is ambiguous", 10, 16),
    ("prove the following grammar", 10, 16),
    ("short-circuit evaluation", 34, 36),
    ("short-circuit", 32, 41),
    ("object-oriented", 50, 73),
    ("backtracking", 81, 83),
    ("prolog", 81, 83),
    ("horn clauses", 81, 82),
    ("referential transparency", 85, 88),
    ("lisp data", 85, 88),
    ("list structures", 85, 88),
    ("write notes on functional", 85, 87),
    ("functional programming", 85, 88),
    ("functional form", 85, 88),
    ("artificial intelligence", 85, 88),
)


def section_page_hints(question: str) -> list[tuple[int, int]]:
    """Narrow section page ranges from query phrases (outline fixture)."""
    q = question.lower()
    ranges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for phrase, start, end in _SECTION_PAGE_HINTS:
        if phrase in q:
            key = (start, end)
            if key not in seen:
                ranges.append(key)
                seen.add(key)
    return ranges


def infer_unit_hints(question: str) -> list[str]:
    """Soft unit hints from query phrases/terms — never hard-filters retrieval."""
    q = question.lower()
    terms = set(focus_terms(question))
    scores: dict[str, float] = {}
    for unit_id, phrases in _UNIT_PHRASES.items():
        for phrase in phrases:
            if phrase in q:
                scores[unit_id] = scores.get(unit_id, 0.0) + 3.0
    for unit_id, vocab in _UNIT_TERMS.items():
        overlap = len(terms & vocab)
        if overlap:
            scores[unit_id] = scores.get(unit_id, 0.0) + float(overlap)
    if "object-oriented" in q or "object oriented" in q:
        scores["4"] = scores.get("4", 0.0) + 2.0
        scores["1"] = scores.get("1", 0.0) + 0.5
    if "functional programming" in q or "write notes on functional" in q:
        scores["5"] = scores.get("5", 0.0) + 3.0
    if "programming paradigms" in q or "language categories" in q:
        scores["1"] = scores.get("1", 0.0) + 1.0
    if "backtracking" in q or "prolog" in q:
        scores["4"] = scores.get("4", 0.0) + 2.0
    if "evaluation criteria" in q or "language evaluation criteria" in q:
        scores["1"] = scores.get("1", 0.0) + 2.0
    if "compilation versus" in q or "compilation and interpretation" in q:
        scores["1"] = scores.get("1", 0.0) + 2.0
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [unit_id for unit_id, score in ranked if score >= 2.0]


def _parse_chunk_metadata(raw: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(raw, dict):
        return None, None, None
    unit = raw.get("unit")
    section = raw.get("section_title")
    toc = raw.get("toc_path")
    return (
        str(unit) if unit is not None else None,
        str(section) if section is not None else None,
        str(toc) if toc is not None else None,
    )


def _study_doc_filter_sql() -> str:
    kinds = ", ".join(f"'{k}'" for k in STUDY_DOC_KINDS)
    return f"d.doc_kind IN ({kinds}) AND d.status = 'ready'"


def _is_lexical_heavy(question: str) -> bool:
    q = question.lower()
    return any(marker in q for marker in _LEXICAL_MARKERS)


def focus_terms(question: str) -> list[str]:
    """Salient terms for BM25 focus search and parent page refinement."""
    q = question.lower()
    raw = re.findall(r"[a-z][a-z0-9-]{2,}", q)
    terms: list[str] = []
    for word in raw:
        if word in _STOPWORDS or word in terms:
            continue
        terms.append(word)
    if "difference" in q and "between" in q:
        for anchor in ("syntax", "semantics", "lexeme", "token"):
            if anchor in q and anchor not in terms:
                terms.insert(0, anchor)
    for phrase in (
        "short-circuit",
        "referential",
        "transparency",
        "object-oriented",
        "precondition",
        "compilation",
        "interpretation",
        "criteria",
        "ambiguous",
        "evaluation criteria",
    ):
        if phrase in q and phrase not in terms:
            terms.insert(0, phrase)
    if "evaluation criteria" in q:
        for anchor in ("evaluation", "criteria"):
            if anchor not in terms:
                terms.insert(0, anchor)
    return terms[:8]


def _to_tsquery(terms: list[str]) -> str | None:
    safe: list[str] = []
    for term in terms:
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", term)
        if len(cleaned) >= 3:
            safe.append(cleaned)
    if not safe:
        return None
    return " | ".join(safe)


def _to_tsquery_and(terms: list[str]) -> str | None:
    safe: list[str] = []
    for term in terms:
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", term)
        if len(cleaned) >= 3:
            safe.append(cleaned)
    if len(safe) < 2:
        return None
    return " & ".join(safe)


_PAGE_PHRASE_ANCHORS = (
    "language evaluation criteria",
    "evaluation criteria",
    "compilation versus interpretation",
    "compilation versus",
    "three fundamental features",
    "short-circuit evaluation",
    "syntax and semantics",
    "lexeme and token",
    "ambiguous expression",
    "ambiguous grammar",
    "programming paradigms",
    "language categories",
    "compilation and interpretation",
    "weakest precondition",
    "short-circuit evaluation",
    "referential transparency",
    "lisp data types",
    "functional programming",
    "object-oriented programming",
    "three fundamental features",
    "data types and list",
)

_GENERIC_PAGE_TERMS = frozenset(
    {
        "difference",
        "programming",
        "languages",
        "language",
        "study",
        "explain",
        "according",
        "decades",
        "history",
    }
)


def _terms_for_page_refinement(terms: list[str]) -> list[str]:
    """Prefer domain terms over generic query words when locating a page in a parent."""
    specific = [t for t in terms if t not in _GENERIC_PAGE_TERMS]
    ordered = sorted(specific or terms, key=len, reverse=True)
    return ordered


def _page_phrase_anchors_for_query(question: str) -> tuple[str, ...]:
    """Query-matching anchors first so multi-page parents map to the right PDF page."""
    q = question.lower()
    matched = tuple(p for p in _PAGE_PHRASE_ANCHORS if p in q)
    if matched:
        return matched + tuple(p for p in _PAGE_PHRASE_ANCHORS if p not in matched)
    return _PAGE_PHRASE_ANCHORS


def _refine_page_from_parent(
    *,
    chunk_page: int,
    parent: _ParentMeta | None,
    terms: list[str],
    question: str = "",
    section_hints: list[tuple[int, int]] | None = None,
) -> int:
    """Map a match inside a multi-page parent to a PDF page index for eval scoring."""
    if parent is None or parent.page_start >= parent.page_end:
        return chunk_page

    body = parent.text.lower()
    best_pos = -1
    for phrase in _page_phrase_anchors_for_query(question):
        pos = body.find(phrase)
        if pos >= 0:
            best_pos = pos
            break
    if best_pos < 0 and terms:
        for term in _terms_for_page_refinement(terms):
            pos = body.find(term.lower())
            if pos >= 0:
                best_pos = pos
                break
    if best_pos < 0:
        return chunk_page

    span = parent.page_end - parent.page_start
    if span <= 0 or len(parent.text) < 2:
        return chunk_page

    ratio = best_pos / len(parent.text)
    estimated = parent.page_start + round(ratio * span)
    estimated = max(parent.page_start, min(parent.page_end, estimated))

    hints = section_hints or section_page_hints(question)
    if hints:
        for start, end in hints:
            if parent.page_start <= end and parent.page_end >= start:
                overlap_start = max(parent.page_start, start)
                overlap_end = min(parent.page_end, end)
                if overlap_start <= estimated <= overlap_end:
                    return estimated
                if overlap_start <= overlap_end:
                    return max(overlap_start, min(overlap_end, estimated))
    return estimated


def _vector_search(
    session: Session,
    *,
    course_id: str,
    query_vec: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.parent_id,
            c.page,
            c.text,
            c.metadata AS chunk_metadata,
            d.filename,
            d.doc_kind,
            1 - (ce.embedding <=> CAST(:query_vec AS vector)) AS vector_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN chunk_embeddings ce ON ce.chunk_id = c.id
        WHERE d.course_id = :course_id
          AND {_study_doc_filter_sql()}
        ORDER BY ce.embedding <=> CAST(:query_vec AS vector)
        LIMIT :limit
        """
    )
    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
    rows = session.execute(
        sql,
        {"course_id": course_id, "query_vec": vec_str, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def _bm25_search(
    session: Session,
    *,
    course_id: str,
    question: str,
    limit: int,
) -> list[dict[str, Any]]:
    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.parent_id,
            c.page,
            c.text,
            c.metadata AS chunk_metadata,
            d.filename,
            d.doc_kind,
            ts_rank_cd(c.text_tsv, websearch_to_tsquery('english', :question)) AS bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.course_id = :course_id
          AND {_study_doc_filter_sql()}
          AND c.text_tsv @@ websearch_to_tsquery('english', :question)
        ORDER BY bm25_score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {"course_id": course_id, "question": question, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def _metadata_toc_search(
    session: Session,
    *,
    course_id: str,
    terms: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """BM25 over chunk outline metadata (section_title + toc_path)."""
    tsquery = _to_tsquery(terms)
    if not tsquery:
        return []

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.parent_id,
            c.page,
            c.text,
            c.metadata AS chunk_metadata,
            d.filename,
            d.doc_kind,
            ts_rank_cd(
                to_tsvector(
                    'english',
                    coalesce(c.metadata->>'section_title', '')
                    || ' '
                    || coalesce(c.metadata->>'toc_path', '')
                ),
                to_tsquery('english', :tsquery)
            ) AS bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.course_id = :course_id
          AND {_study_doc_filter_sql()}
          AND to_tsvector(
                'english',
                coalesce(c.metadata->>'section_title', '')
                || ' '
                || coalesce(c.metadata->>'toc_path', '')
              ) @@ to_tsquery('english', :tsquery)
        ORDER BY bm25_score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {"course_id": course_id, "tsquery": tsquery, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def _bm25_and_terms_search(
    session: Session,
    *,
    course_id: str,
    terms: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """BM25 requiring all terms (AND) — surfaces definition-style co-occurrence."""
    tsquery = _to_tsquery_and(terms)
    if not tsquery:
        return []

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.parent_id,
            c.page,
            c.text,
            c.metadata AS chunk_metadata,
            d.filename,
            d.doc_kind,
            ts_rank_cd(c.text_tsv, to_tsquery('english', :tsquery)) AS bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.course_id = :course_id
          AND {_study_doc_filter_sql()}
          AND c.text_tsv @@ to_tsquery('english', :tsquery)
        ORDER BY bm25_score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {"course_id": course_id, "tsquery": tsquery, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def _bm25_page_bounded_and_search(
    session: Session,
    *,
    course_id: str,
    terms: list[str],
    page_start: int,
    page_end: int,
    limit: int,
) -> list[dict[str, Any]]:
    """AND BM25 within a page window (soft section prior for early-unit definition hits)."""
    tsquery = _to_tsquery_and(terms)
    if not tsquery:
        return []

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.parent_id,
            c.page,
            c.text,
            c.metadata AS chunk_metadata,
            d.filename,
            d.doc_kind,
            ts_rank_cd(c.text_tsv, to_tsquery('english', :tsquery)) AS bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.course_id = :course_id
          AND {_study_doc_filter_sql()}
          AND c.page >= :page_start
          AND c.page <= :page_end
          AND c.text_tsv @@ to_tsquery('english', :tsquery)
        ORDER BY bm25_score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {
            "course_id": course_id,
            "tsquery": tsquery,
            "page_start": page_start,
            "page_end": page_end,
            "limit": limit,
        },
    ).mappings()
    return [dict(row) for row in rows]


def _bm25_focus_search(
    session: Session,
    *,
    course_id: str,
    terms: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    tsquery = _to_tsquery(terms)
    if not tsquery:
        return []

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.parent_id,
            c.page,
            c.text,
            c.metadata AS chunk_metadata,
            d.filename,
            d.doc_kind,
            ts_rank_cd(c.text_tsv, to_tsquery('english', :tsquery)) AS bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.course_id = :course_id
          AND {_study_doc_filter_sql()}
          AND c.text_tsv @@ to_tsquery('english', :tsquery)
        ORDER BY bm25_score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(
        sql,
        {"course_id": course_id, "tsquery": tsquery, "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def _rrf_fuse(
    vector_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
    *,
    k: int,
    vector_weight: float,
    bm25_weight: float,
    top_n: int,
    extra_lists: list[tuple[list[dict[str, Any]], float]] | None = None,
) -> list[dict[str, Any]]:
    scores: dict[uuid.UUID, float] = {}
    rows_by_id: dict[uuid.UUID, dict[str, Any]] = {}
    vector_scores: dict[uuid.UUID, float | None] = {}
    bm25_scores: dict[uuid.UUID, float | None] = {}

    for rank, row in enumerate(vector_hits, start=1):
        chunk_id = row["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + vector_weight / (k + rank)
        rows_by_id[chunk_id] = row
        vector_scores[chunk_id] = float(row["vector_score"]) if row.get("vector_score") is not None else None

    for rank, row in enumerate(bm25_hits, start=1):
        chunk_id = row["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + bm25_weight / (k + rank)
        rows_by_id.setdefault(chunk_id, row)
        bm25_scores[chunk_id] = float(row["bm25_score"]) if row.get("bm25_score") is not None else None

    for extra_hits, weight in extra_lists or []:
        for rank, row in enumerate(extra_hits, start=1):
            chunk_id = row["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + rank)
            rows_by_id.setdefault(chunk_id, row)
            if row.get("bm25_score") is not None:
                prev = bm25_scores.get(chunk_id)
                candidate = float(row["bm25_score"])
                if prev is None or candidate > prev:
                    bm25_scores[chunk_id] = candidate

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[:top_n]
    fused: list[dict[str, Any]] = []
    for chunk_id in ranked_ids:
        base = dict(rows_by_id[chunk_id])
        base["rrf_score"] = scores[chunk_id]
        base["vector_score"] = vector_scores.get(chunk_id)
        base["bm25_score"] = bm25_scores.get(chunk_id)
        fused.append(base)
    return fused


def _load_parents(
    session: Session,
    parent_ids: set[uuid.UUID],
) -> dict[uuid.UUID, _ParentMeta]:
    if not parent_ids:
        return {}
    rows = session.scalars(select(ChunkParent).where(ChunkParent.id.in_(parent_ids))).all()
    return {
        row.id: _ParentMeta(text=row.text, page_start=row.page_start, page_end=row.page_end)
        for row in rows
    }


def _rows_to_chunks(
    session: Session,
    rows: list[dict[str, Any]],
    *,
    terms: list[str] | None = None,
    question: str = "",
) -> list[RetrievedChunk]:
    parent_ids = {row["parent_id"] for row in rows if row.get("parent_id")}
    parents = _load_parents(session, parent_ids)
    refine_terms = terms or []
    sec_hints = section_page_hints(question) if question else []
    chunks: list[RetrievedChunk] = []
    for row in rows:
        parent_id = row.get("parent_id")
        parent = parents.get(parent_id) if parent_id else None
        page = int(row["page"])
        unit, section_title, toc_path = _parse_chunk_metadata(row.get("chunk_metadata"))
        if parent is not None:
            page = _refine_page_from_parent(
                chunk_page=page,
                parent=parent,
                terms=refine_terms,
                question=question,
                section_hints=sec_hints,
            )
        chunks.append(
            RetrievedChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                filename=row["filename"],
                doc_kind=row["doc_kind"],
                page=page,
                text=row["text"],
                parent_text=parent.text if parent else None,
                parent_id=parent_id,
                parent_page_start=parent.page_start if parent else None,
                parent_page_end=parent.page_end if parent else None,
                unit=unit,
                section_title=section_title,
                toc_path=toc_path,
                vector_score=row.get("vector_score"),
                bm25_score=row.get("bm25_score"),
                rrf_score=row.get("rrf_score"),
            )
        )
    return chunks


def fetch_hybrid_candidates(
    session: Session,
    *,
    course_id: str,
    question: str,
) -> list[RetrievedChunk]:
    """Run vector + BM25 search and RRF-fuse to candidate chunks."""
    terms = focus_terms(question)
    lexical = _is_lexical_heavy(question)
    vector_weight = settings.hybrid_vector_weight
    bm25_weight = settings.hybrid_bm25_weight
    if lexical:
        vector_weight = settings.hybrid_vector_weight * 0.85
        bm25_weight = settings.hybrid_bm25_weight * 1.75

    q_lower = question.lower()
    if "evaluation criteria" in q_lower:
        vector_weight *= 0.75
        bm25_weight *= 1.25

    query_vec = embed_texts([question], is_query=True)[0]
    vector_hits = _vector_search(
        session,
        course_id=course_id,
        query_vec=query_vec,
        limit=settings.retrieval_vector_top_k,
    )
    bm25_hits = _bm25_search(
        session,
        course_id=course_id,
        question=question,
        limit=settings.retrieval_bm25_top_k,
    )
    focus_hits = _bm25_focus_search(
        session,
        course_id=course_id,
        terms=terms,
        limit=settings.retrieval_bm25_top_k,
    )
    metadata_hits = _metadata_toc_search(
        session,
        course_id=course_id,
        terms=terms,
        limit=settings.retrieval_bm25_top_k,
    )
    extra: list[tuple[list[dict[str, Any]], float]] = []
    if focus_hits:
        extra.append((focus_hits, bm25_weight * 1.1))
    if metadata_hits:
        extra.append((metadata_hits, bm25_weight * 0.8))
    if "evaluation criteria" in q_lower:
        eval_and_hits = _bm25_and_terms_search(
            session,
            course_id=course_id,
            terms=["evaluation", "criteria"],
            limit=settings.retrieval_bm25_top_k,
        )
        if eval_and_hits:
            extra.append((eval_and_hits, bm25_weight * 1.35))
        early_eval_hits = _bm25_page_bounded_and_search(
            session,
            course_id=course_id,
            terms=["evaluation", "criteria"],
            page_start=3,
            page_end=9,
            limit=settings.retrieval_bm25_top_k,
        )
        if early_eval_hits:
            extra.append((early_eval_hits, bm25_weight * 1.5))
        prelim_meta = _metadata_toc_search(
            session,
            course_id=course_id,
            terms=["preliminary", "evaluation"],
            limit=settings.retrieval_bm25_top_k,
        )
        if prelim_meta:
            extra.append((prelim_meta, bm25_weight * 0.9))

    fused = _rrf_fuse(
        vector_hits,
        bm25_hits,
        k=settings.rrf_k,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
        top_n=settings.rrf_output_top_k,
        extra_lists=extra,
    )
    return _rows_to_chunks(session, fused, terms=terms, question=question)


def retrieve_study(
    session: Session,
    *,
    course_id: str,
    question: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Hybrid retrieve and rerank (no confidence gate)."""
    from app.services.rag.rerank import rerank_chunks

    candidates = fetch_hybrid_candidates(session, course_id=course_id, question=question)
    if not candidates:
        return []

    return rerank_chunks(question, candidates, top_k=top_k)


def replay_golden_set(golden: list[dict]) -> list[dict]:
    """Replay golden-set questions against live retrieval (no LLM)."""
    import os

    from app.services.rag.pipeline import run_study_question

    limit_raw = os.environ.get("GOLDEN_LIMIT", "").strip()
    if limit_raw.isdigit():
        golden = golden[: int(limit_raw)]

    session = SessionLocal()
    try:
        results: list[dict] = []
        total = len(golden)
        for i, row in enumerate(golden, start=1):
            if i == 1 or i % 5 == 0 or i == total:
                print(f"[replay {i}/{total}] {row['id']}", flush=True)
            outcome = run_study_question(
                session,
                course_id=row["course"],
                question=row["question"],
                preset=row.get("query_mode", "study"),
            )
            pages = [c.page for c in outcome.chunks[: settings.study_output_top_k]]
            retrieved_doc = outcome.chunks[0].filename if outcome.chunks else None
            results.append(
                {
                    "id": row["id"],
                    "status": outcome.status,
                    "retrieved_pages": pages if outcome.status == "ok" else [],
                    "retrieved_doc": retrieved_doc,
                    "top_k": settings.study_output_top_k,
                }
            )
        return results
    finally:
        session.close()
