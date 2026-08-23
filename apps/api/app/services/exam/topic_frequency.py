"""Topic/unit frequency report from past_paper chunks (no LLM).

Combines a human-reviewable PYQ seed YAML (primary for v1) with keyword matching
against outline section titles and golden-set unit terms for readable chunk text
on pages not covered by the seed. Study retrieval is unaffected — read-only DB access.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chunk, Course, Document, ExamQuestion
from app.services.course_outline import notes_fallback_label, resolve_course_outline
from app.services.outline_hints import build_unit_phrases_from_outline, build_unit_terms_from_outline
from app.services.pdf_extract import DocumentOutline, OutlineUnit, load_outline, _section_count

_REPO_ROOT = Path(__file__).resolve().parents[5]
_READABLE_CHAR_THRESHOLD = 100

# PPL seed/golden supplements (generic courses use outline-derived phrases only).
from app.services.rag.retrieve import _UNIT_PHRASES, _UNIT_TERMS  # noqa: E402

_SEED_PATHS: dict[str, Path] = {
    "PPL": _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_pyq_seed.yaml",
}
_FALLBACK_SECTION = "Unclassified"


@dataclass
class PastPaperChunkRow:
    document_id: str
    filename: str
    page: int
    text: str


@dataclass
class SeedQuestion:
    unit: str
    section_title: str
    page: int


@dataclass
class _CountState:
    unit_counts: dict[str, int] = field(default_factory=dict)
    section_counts: dict[tuple[str, str], int] = field(default_factory=dict)

    def add(self, unit_id: str, section_title: str, amount: int = 1) -> None:
        self.unit_counts[unit_id] = self.unit_counts.get(unit_id, 0) + amount
        key = (unit_id, section_title)
        self.section_counts[key] = self.section_counts.get(key, 0) + amount


def count_parsed_questions(
    session: Session,
    course_id: str,
    *,
    document_ids: list[uuid.UUID] | None = None,
) -> int:
    stmt = select(func.count(ExamQuestion.id)).where(ExamQuestion.course_id == course_id)
    if document_ids:
        stmt = stmt.where(ExamQuestion.document_id.in_(document_ids))
    return session.scalar(stmt) or 0


def _count_from_exam_questions(
    session: Session,
    course_id: str,
    outline: DocumentOutline | None,
    *,
    document_ids: list[uuid.UUID] | None = None,
) -> _CountState | None:
    """Return unit/section counts from parsed exam_questions rows, or None when empty."""
    if count_parsed_questions(session, course_id, document_ids=document_ids) == 0:
        return None

    stmt = select(ExamQuestion.unit, ExamQuestion.section_title).where(
        ExamQuestion.course_id == course_id
    )
    if document_ids:
        stmt = stmt.where(ExamQuestion.document_id.in_(document_ids))
    state = _CountState()
    for unit, section_title in session.execute(stmt).all():
        unit_id = str(unit) if unit else _fallback_unit_id(outline)
        section = str(section_title) if section_title else _FALLBACK_SECTION
        state.add(unit_id, section)
    return state


def _exam_questions_coverage_note(session: Session, course_id: str, total: int) -> str:
    rows = session.execute(
        select(ExamQuestion.extraction_method, func.count())
        .where(ExamQuestion.course_id == course_id)
        .group_by(ExamQuestion.extraction_method)
        .order_by(ExamQuestion.extraction_method)
    ).all()
    method_summary = ", ".join(f"{count} via {method}" for method, count in rows)
    return (
        f"{total} parsed question(s) from exam_questions "
        f"({method_summary or 'no extraction_method rows'})."
    )


def _outline_path(course_id: str) -> Path | None:
    """PPL fixture path — used only when tests inject explicit outline_path."""
    from app.services.course_outline import outline_path_for_course

    return outline_path_for_course(course_id)


def _fallback_unit_id(outline: DocumentOutline | None) -> str:
    if outline and outline.units:
        return outline.units[0].id
    return "general"


def _count_generic_past_papers(
    session: Session,
    course_id: str,
    outline: DocumentOutline | None,
    chunks: list[PastPaperChunkRow],
) -> _CountState:
    """Count readable past_paper pages via keyword match against outline section titles."""
    state = _CountState()
    fallback_unit = _fallback_unit_id(outline)
    patterns = _build_keyword_patterns(outline) if outline is not None else []
    seen_pages: set[tuple[str, int]] = set()

    for row in chunks:
        if len(row.text.strip()) < _READABLE_CHAR_THRESHOLD:
            continue
        key = (row.filename, row.page)
        if key in seen_pages:
            continue
        seen_pages.add(key)

        if patterns:
            match = _best_keyword_match(row.text, patterns)
            if match is not None:
                state.add(match[0], match[1])
                continue

        state.add(fallback_unit, _FALLBACK_SECTION)

    return state


def _rollup_state_to_units(state: _CountState, outline: DocumentOutline) -> list[dict[str, Any]]:
    """Aggregate section-level keyword counts to unit (chapter) level for display."""
    serialized = _serialize_units(outline, state)
    return [
        {
            "unit": unit["unit"],
            "title": unit["title"],
            "count": unit["count"],
            "sections": [],
        }
        for unit in serialized
    ]


def _should_aggregate_to_units(outline: DocumentOutline | None) -> bool:
    return outline is not None and _section_count(outline) > 12


def _serialize_generic_units(
    outline: DocumentOutline | None,
    state: _CountState,
    *,
    fallback_title: str,
    include_section_detail: bool = False,
) -> list[dict[str, Any]]:
    if outline is not None:
        if include_section_detail or not _should_aggregate_to_units(outline):
            return _serialize_units(outline, state)
        return _rollup_state_to_units(state, outline)

    total = sum(state.unit_counts.values())
    if total <= 0:
        return []

    return [
        {
            "unit": "general",
            "title": fallback_title,
            "count": total,
            "sections": [{"section_title": _FALLBACK_SECTION, "count": total}],
        }
    ]


def _seed_path(course_id: str) -> Path | None:
    path = _SEED_PATHS.get(course_id.upper())
    return path if path and path.is_file() else None


@lru_cache(maxsize=4)
def _load_seed(course_id: str) -> dict[str, Any] | None:
    path = _SEED_PATHS.get(course_id.upper())
    if path is None or not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_seed_questions(course_id: str) -> tuple[list[SeedQuestion], set[int], str]:
    """Return seed questions, covered page set, and coverage note."""
    raw = _load_seed(course_id)
    if not raw:
        return [], set(), "No PYQ seed file for this course."

    covered = {int(p) for p in raw.get("covered_pages") or []}
    note = str(raw.get("coverage_note") or "partial PYQ seed")
    questions: list[SeedQuestion] = []
    for entry in raw.get("questions") or []:
        questions.append(
            SeedQuestion(
                unit=str(entry["unit"]),
                section_title=str(entry["section_title"]),
                page=int(entry.get("page", 0)),
            )
        )
    return questions, covered, note


def _fetch_past_paper_documents(session: Session, course_id: str) -> list[Document]:
    stmt = select(Document).where(
        Document.course_id == course_id,
        Document.doc_kind == "past_paper",
        Document.status == "ready",
    )
    return list(session.scalars(stmt).all())


def _fetch_past_paper_chunks(session: Session, course_id: str) -> list[PastPaperChunkRow]:
    stmt = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Document.course_id == course_id,
            Document.doc_kind == "past_paper",
            Document.status == "ready",
        )
        .order_by(Document.filename, Chunk.page, Chunk.chunk_index)
    )
    rows: list[PastPaperChunkRow] = []
    for chunk, doc in session.execute(stmt).all():
        rows.append(
            PastPaperChunkRow(
                document_id=str(doc.id),
                filename=doc.filename,
                page=chunk.page,
                text=chunk.text or "",
            )
        )
    return rows


def _build_keyword_patterns(outline: DocumentOutline) -> list[tuple[str, str, list[str]]]:
    """(unit_id, section_title, phrases) sorted longest phrase first."""
    unit_phrases_map = build_unit_phrases_from_outline(outline)
    unit_terms_map = build_unit_terms_from_outline(outline)
    patterns: list[tuple[str, str, list[str]]] = []
    for unit in outline.units:
        unit_phrases = list(unit_phrases_map.get(unit.id, ()))
        unit_terms = set(unit_terms_map.get(unit.id, frozenset()))
        unit_phrases.extend(_UNIT_PHRASES.get(unit.id, ()))
        unit_terms.update(_UNIT_TERMS.get(unit.id, ()))
        for section in unit.sections:
            phrases: list[str] = []
            title_lower = section.title.lower()
            phrases.append(title_lower)
            unit_title_lower = unit.title.lower()
            if unit_title_lower and unit_title_lower not in phrases:
                phrases.append(unit_title_lower)
            for token in re.split(r"[^a-z0-9]+", title_lower):
                if len(token) >= 5:
                    phrases.append(token)
            phrases.extend(unit_phrases)
            phrases.extend(unit_terms)
            # Dedupe preserving order; prefer longer phrases first when matching.
            seen: set[str] = set()
            unique: list[str] = []
            for phrase in sorted({p.lower().strip() for p in phrases if p and len(p.strip()) >= 4}, key=len, reverse=True):
                if phrase not in seen:
                    seen.add(phrase)
                    unique.append(phrase)
            patterns.append((unit.id, section.title, unique))
    return patterns


def _best_keyword_match(
    text: str,
    patterns: list[tuple[str, str, list[str]]],
) -> tuple[str, str] | None:
    hay = text.lower()
    best: tuple[str, str, int] | None = None
    for unit_id, section_title, phrases in patterns:
        score = 0
        for phrase in phrases:
            if phrase in hay:
                score += len(phrase)
        if score > 0 and (best is None or score > best[2]):
            best = (unit_id, section_title, score)
    if best is None:
        return None
    return best[0], best[1]


def _empty_units(outline: DocumentOutline | None) -> list[dict[str, Any]]:
    if outline is None:
        return []
    units: list[dict[str, Any]] = []
    for unit in outline.units:
        units.append(
            {
                "unit": unit.id,
                "title": unit.title,
                "count": 0,
                "sections": [
                    {"section_title": section.title, "count": 0} for section in unit.sections
                ],
            }
        )
    return units


def _serialize_units(outline: DocumentOutline, state: _CountState) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for unit in outline.units:
        defined_titles = {section.title for section in unit.sections}
        sections = [
            {
                "section_title": section.title,
                "count": state.section_counts.get((unit.id, section.title), 0),
            }
            for section in unit.sections
        ]
        for (unit_id, section_title), count in state.section_counts.items():
            if unit_id == unit.id and section_title not in defined_titles and count > 0:
                sections.append({"section_title": section_title, "count": count})
        units.append(
            {
                "unit": unit.id,
                "title": unit.title,
                "count": state.unit_counts.get(unit.id, 0),
                "sections": sections,
            }
        )
    return units


def _source_documents(chunks: list[PastPaperChunkRow]) -> list[dict[str, Any]]:
    by_file: dict[str, dict[str, Any]] = {}
    for row in chunks:
        entry = by_file.setdefault(
            row.filename,
            {"filename": row.filename, "readable_pages": set(), "chunk_count": 0},
        )
        entry["chunk_count"] += 1
        if len(row.text.strip()) >= _READABLE_CHAR_THRESHOLD:
            entry["readable_pages"].add(row.page)
    result: list[dict[str, Any]] = []
    for entry in by_file.values():
        result.append(
            {
                "filename": entry["filename"],
                "readable_pages": sorted(entry["readable_pages"]),
                "chunk_count": entry["chunk_count"],
            }
        )
    return sorted(result, key=lambda item: item["filename"])


def _build_coverage_note(
    seed_note: str,
    source_documents: list[dict[str, Any]],
    documents: list[Document],
    covered_pages: set[int],
) -> str:
    """Prefer live ingest readability over stale seed YAML notes after OCR."""
    if not source_documents:
        return seed_note

    total_pages = max((doc.page_count or 0 for doc in documents), default=0)
    readable_pages: set[int] = set()
    for entry in source_documents:
        readable_pages.update(entry.get("readable_pages") or [])

    readable_count = len(readable_pages)
    if total_pages <= 0:
        return seed_note

    if readable_count >= total_pages - 1:
        seed_detail = (
            f"seed maps {len(covered_pages)} page(s) in detail"
            if covered_pages
            else "keyword estimates on remaining pages"
        )
        return (
            f"full — OCR complete; {readable_count}/{total_pages} pages readable; "
            f"{seed_detail}, other pages via keyword estimate"
        )

    pending = total_pages - readable_count
    if readable_count > len(covered_pages):
        return (
            f"partial — {readable_count}/{total_pages} pages readable after OCR; "
            f"{pending} page(s) still low-text; seed covers page(s) {sorted(covered_pages)}"
        )

    return seed_note


def compute_topic_frequency(
    session: Session,
    course_id: str,
    *,
    outline_path: Path | None = None,
    seed_path: Path | None = None,
    include_section_detail: bool = False,
    document_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """Build topic frequency JSON for a course from past_paper chunks + seed or page counts."""
    course = session.get(Course, course_id)
    if course is None:
        return {"found": False, "course_id": course_id}

    if outline_path is not None:
        outline = load_outline(outline_path)
    else:
        outline, _source = resolve_course_outline(session, course_id)

    documents = _fetch_past_paper_documents(session, course_id)
    if document_ids:
        allowed = set(document_ids)
        documents = [document for document in documents if document.id in allowed]
    chunks = _fetch_past_paper_chunks(session, course_id)
    if document_ids:
        allowed_filenames = {document.filename for document in documents}
        chunks = [row for row in chunks if row.filename in allowed_filenames]
    if not documents:
        return {
            "found": True,
            "course_id": course_id,
            "total_questions_estimated": 0,
            "coverage_note": "No past_paper documents ingested for this course.",
            "units": _empty_units(outline),
            "source_documents": [],
        }

    db_state = _count_from_exam_questions(session, course_id, outline, document_ids=document_ids)
    if db_state is not None:
        total = sum(db_state.unit_counts.values())
        source_documents = _source_documents(chunks)
        fallback_title = notes_fallback_label(session, course_id)
        units = _serialize_generic_units(
            outline,
            db_state,
            fallback_title=fallback_title,
            include_section_detail=include_section_detail,
        )
        return {
            "found": True,
            "course_id": course_id,
            "total_questions_estimated": total,
            "coverage_note": _exam_questions_coverage_note(session, course_id, total),
            "units": units,
            "source_documents": source_documents,
        }

    has_seed_file = seed_path is not None or _seed_path(course_id) is not None

    # Seed (primary for PPL fixture courses)
    if seed_path is not None:
        raw_seed = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
        seed_questions = [
            SeedQuestion(
                unit=str(entry["unit"]),
                section_title=str(entry["section_title"]),
                page=int(entry.get("page", 0)),
            )
            for entry in raw_seed.get("questions") or []
        ]
        covered_pages = {int(p) for p in raw_seed.get("covered_pages") or []}
        seed_note = str(raw_seed.get("coverage_note") or "partial PYQ seed")
    else:
        seed_questions, covered_pages, seed_note = load_seed_questions(course_id)

    if has_seed_file and seed_questions:
        state = _CountState()
        for question in seed_questions:
            state.add(question.unit, question.section_title)

        if outline is not None:
            patterns = _build_keyword_patterns(outline)
            seen_unseeded_pages: set[tuple[str, int]] = set()
            for row in chunks:
                if len(row.text.strip()) < _READABLE_CHAR_THRESHOLD:
                    continue
                if row.page in covered_pages:
                    continue
                key = (row.filename, row.page)
                if key in seen_unseeded_pages:
                    continue
                match = _best_keyword_match(row.text, patterns)
                if match is not None:
                    state.add(match[0], match[1])
                    seen_unseeded_pages.add(key)

        total = sum(state.unit_counts.values())
        units = _serialize_units(outline, state) if outline else []
        source_documents = _source_documents(chunks)
        return {
            "found": True,
            "course_id": course_id,
            "total_questions_estimated": total,
            "coverage_note": _build_coverage_note(seed_note, source_documents, documents, covered_pages),
            "units": units,
            "source_documents": source_documents,
        }

    # Generic courses: keyword match past_paper text to outline sections
    state = _count_generic_past_papers(session, course_id, outline, chunks)
    total = sum(state.unit_counts.values())
    fallback_title = notes_fallback_label(session, course_id)
    units = _serialize_generic_units(
        outline,
        state,
        fallback_title=fallback_title,
        include_section_detail=include_section_detail,
    )
    source_documents = _source_documents(chunks)
    coverage_note = (
        f"Matched {total} past-paper question(s) to outline topics by keyword (no PYQ seed)."
        if total > 0
        else "Past papers ingested but no readable chunk text yet."
    )

    return {
        "found": True,
        "course_id": course_id,
        "total_questions_estimated": total,
        "coverage_note": coverage_note,
        "units": units,
        "source_documents": source_documents,
    }


def compute_topic_frequency_json(session: Session, course_id: str) -> str:
    """CLI helper — pretty JSON string."""
    return json.dumps(compute_topic_frequency(session, course_id), indent=2)
