"""Course outline API — fixture, upload, extracted TOC, or auto-stub (no LLM)."""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chunk, Course, Document
from app.services.pdf_extract import (
    DocumentOutline,
    OutlineGranularity,
    OutlineQuality,
    OutlineSection,
    OutlineUnit,
    annotate_pages_with_outline,
    extract_outline_from_pdf,
    extract_pdf,
    load_outline,
    outline_quality_score,
    outline_summary,
    outline_to_storage_dict,
    parse_outline_data,
)

OutlineSource = Literal["fixture", "uploaded", "extracted", "auto_stub"]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_AUTO_STUB_PAGES_PER_SECTION = 10

_OUTLINE_PATHS: dict[str, Path] = {
    "PPL": _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml",
}


@lru_cache(maxsize=8)
def _load_outline_file(path: str) -> DocumentOutline:
    return load_outline(Path(path))


def outline_path_for_course(course_id: str) -> Path | None:
    path = _OUTLINE_PATHS.get(course_id.upper())
    return path if path and path.is_file() else None


def _stored_outline_source(course: Course) -> OutlineSource | None:
    if not course.outline_data:
        return None
    source = str(course.outline_data.get("outline_source") or "uploaded")
    if source in ("uploaded", "extracted"):
        return source  # type: ignore[return-value]
    return "uploaded"


def _fetch_notes_documents(session: Session, course_id: str) -> list[Document]:
    stmt = (
        select(Document)
        .where(
            Document.course_id == course_id,
            Document.doc_kind == "notes",
            Document.status == "ready",
        )
        .order_by(Document.filename)
    )
    return list(session.scalars(stmt).all())


def _document_page_count(session: Session, document: Document) -> int:
    if document.page_count and document.page_count > 0:
        return document.page_count
    max_page = session.scalar(
        select(func.max(Chunk.page)).where(Chunk.document_id == document.id)
    )
    return int(max_page or 0)


def _build_page_range_sections(unit_title: str, page_count: int, pages_per_section: int) -> list[OutlineSection]:
    sections: list[OutlineSection] = []
    start = 0
    while start < page_count:
        end = min(start + pages_per_section - 1, page_count - 1)
        sections.append(
            OutlineSection(
                title=f"{unit_title} — pages {start + 1}–{end + 1}",
                page_start=start,
                page_end=end,
            )
        )
        start = end + 1
    return sections


def build_auto_stub_outline(session: Session, course_id: str) -> DocumentOutline | None:
    """One unit per ingested notes PDF; sections from fixed page-range buckets."""
    notes_docs = _fetch_notes_documents(session, course_id)
    if not notes_docs:
        return None

    units: list[OutlineUnit] = []
    max_page_end = 0
    for index, document in enumerate(notes_docs, start=1):
        page_count = _document_page_count(session, document)
        if page_count <= 0:
            continue
        stem = Path(document.filename).stem
        sections = _build_page_range_sections(stem, page_count, _AUTO_STUB_PAGES_PER_SECTION)
        page_end = page_count - 1
        units.append(
            OutlineUnit(
                id=str(index),
                title=stem,
                page_start=0,
                page_end=page_end,
                sections=sections,
            )
        )
        max_page_end = max(max_page_end, page_end)

    if not units:
        return None

    return DocumentOutline(
        document=notes_docs[0].filename,
        course=course_id,
        page_index_base=0,
        page_count=max_page_end + 1,
        units=units,
        front_matter=None,
    )


def find_syllabus_document(session: Session, course_id: str) -> Document | None:
    """Return the best syllabus PDF for Course Map promotion, or None."""
    stmt = (
        select(Document)
        .where(
            Document.course_id == course_id,
            Document.status == "ready",
            Document.file_path.isnot(None),
        )
        .order_by(Document.created_at, Document.filename)
    )
    ready: list[Document] = []
    for document in session.scalars(stmt).all():
        if document.file_path and Path(document.file_path).is_file():
            ready.append(document)

    for document in ready:
        if document.doc_kind == "syllabus":
            return document

    for document in ready:
        quality = document.extraction_quality or {}
        if quality.get("upload_intent") == "syllabus":
            return document

    for document in ready:
        if "syllabus" in document.filename.lower():
            return document

    return None


def _match_topic_documents_to_units(
    topics: list,
    units: list[OutlineUnit],
    docs_by_topic: dict[uuid.UUID, list[uuid.UUID]],
) -> dict[int, list[uuid.UUID]]:
    """Map unit index → document ids assigned via matched study topics."""
    topics_sorted = sorted(topics, key=lambda topic: (topic.sort_order, topic.title))
    positional = len(topics_sorted) == len(units)
    matches: dict[int, list[uuid.UUID]] = {}

    for index, topic in enumerate(topics_sorted):
        doc_ids = docs_by_topic.get(topic.id, [])
        if not doc_ids:
            continue

        unit_index: int | None = None
        if positional:
            unit_index = index
        else:
            topic_lower = topic.title.lower()
            for unit_idx, unit in enumerate(units):
                unit_lower = unit.title.lower()
                if topic_lower in unit_lower or unit_lower in topic_lower:
                    unit_index = unit_idx
                    break

        if unit_index is not None and 0 <= unit_index < len(units):
            matches.setdefault(unit_index, []).extend(doc_ids)

    return matches


def _units_with_assigned_documents(
    session: Session,
    course_id: str,
    outline: DocumentOutline,
    *,
    syllabus_document_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Build unit dicts with assigned_document_ids from study topic assignments."""
    from app.services.study_topics import list_study_topics

    base_units = [
        {
            "id": unit.id,
            "title": unit.title,
            "page_start": unit.page_start,
            "page_end": unit.page_end,
            "sections": [
                {
                    "title": section.title,
                    "page_start": section.page_start,
                    "page_end": section.page_end,
                }
                for section in unit.sections
            ],
        }
        for unit in outline.units
    ]

    topics = list_study_topics(session, course_id) or []
    if not topics:
        return base_units

    stmt = select(Document).where(
        Document.course_id == course_id,
        Document.topic_id.isnot(None),
        Document.id != syllabus_document_id,
    )
    docs_by_topic: dict[uuid.UUID, list[uuid.UUID]] = {}
    for document in session.scalars(stmt).all():
        if document.topic_id is None:
            continue
        docs_by_topic.setdefault(document.topic_id, []).append(document.id)

    if not docs_by_topic:
        return base_units

    unit_doc_map = _match_topic_documents_to_units(topics, outline.units, docs_by_topic)
    for unit_index, doc_ids in unit_doc_map.items():
        unique_ids = list(dict.fromkeys(str(doc_id) for doc_id in doc_ids))
        if unique_ids:
            base_units[unit_index]["assigned_document_ids"] = unique_ids

    return base_units


def _extract_syllabus_outline(
    syllabus: Document,
) -> tuple[DocumentOutline, OutlineGranularity | None, OutlineQuality, str | None]:
    file_path = Path(syllabus.file_path)
    extraction = extract_pdf(file_path)
    outline, granularity, quality = extract_outline_from_pdf(file_path, pages=extraction.pages)
    if outline is None or quality is None:
        raise ValueError("outline_extraction_failed")
    if len(outline.units) < 2:
        raise ValueError("outline_extraction_failed")
    if quality == "low":
        raise ValueError("outline_quality_low")
    outline.document = syllabus.filename
    return outline, granularity, quality, outline.extraction_method


def build_outline_for_promotion(
    session: Session,
    course_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Extract syllabus TOC (and merge topic assignments) before mapped promotion."""
    syllabus = find_syllabus_document(session, course_id)
    if syllabus is None:
        raise ValueError("syllabus_document_not_found")

    outline, granularity, quality, extraction_method = _extract_syllabus_outline(syllabus)
    outline.course = course_id

    units_payload = _units_with_assigned_documents(
        session,
        course_id,
        outline,
        syllabus_document_id=syllabus.id,
    )

    if not dry_run:
        course = session.get(Course, course_id)
        if course is None:
            raise ValueError(f"Course not found: {course_id}")
        stored = outline_to_storage_dict(
            outline,
            "extracted",
            outline_granularity=granularity,
            outline_quality=quality,
        )
        stored["units"] = units_payload
        if extraction_method:
            stored["outline_extraction_method"] = extraction_method
        course.outline_data = stored
        session.flush()

    return {
        "outline_source": "extracted",
        "outline_quality": quality,
        "outline_granularity": granularity,
        "unit_count": len(outline.units),
        "unit_titles": [unit.title for unit in outline.units],
        "units": units_payload,
    }


def resolve_course_outline(session: Session, course_id: str) -> tuple[DocumentOutline | None, OutlineSource | None]:
    """
    Resolution order:
    1. PPL fixture YAML
    2. DB outline_data with outline_source=uploaded
    3. DB outline_data with outline_source=extracted
    4. Live auto-stub page buckets
    """
    course = session.get(Course, course_id)
    if course is None:
        return None, None

    fixture_path = outline_path_for_course(course_id)
    if fixture_path is not None:
        return _load_outline_file(str(fixture_path)), "fixture"

    stored_source = _stored_outline_source(course)
    if course.outline_data and stored_source == "uploaded":
        return parse_outline_data(course.outline_data), "uploaded"

    if course.outline_data and stored_source == "extracted":
        return parse_outline_data(course.outline_data), "extracted"

    if (
        course.structure_mode == "mapped"
        and find_syllabus_document(session, course_id) is not None
        and course.outline_data
        and str(course.outline_data.get("outline_source")) == "extracted"
    ):
        return parse_outline_data(course.outline_data), "extracted"

    if course.structure_mode == "mapped" and find_syllabus_document(session, course_id) is not None:
        return None, None

    stub = build_auto_stub_outline(session, course_id)
    if stub is not None:
        return stub, "auto_stub"

    return None, None


def _outline_granularity(
    course: Course | None,
    source: OutlineSource | None,
) -> OutlineGranularity | None:
    if course and course.outline_data and course.outline_data.get("outline_granularity"):
        return course.outline_data["outline_granularity"]  # type: ignore[return-value]
    if source == "auto_stub":
        return "page_stub"
    if source == "fixture":
        return "chapter"
    return None


def _outline_quality(
    course: Course | None,
    source: OutlineSource | None,
) -> OutlineQuality | None:
    if course and course.outline_data and course.outline_data.get("outline_quality"):
        return course.outline_data["outline_quality"]  # type: ignore[return-value]
    if source == "auto_stub":
        return "low"
    if source == "fixture":
        return "high"
    return None


def serialize_course_outline(
    outline: DocumentOutline,
    course_id: str,
    *,
    outline_source: OutlineSource | None = None,
    outline_granularity: OutlineGranularity | None = None,
    outline_quality: OutlineQuality | None = None,
) -> dict[str, Any]:
    """JSON shape for GET /api/v1/courses/{course_id}/outline."""
    front_matter = None
    if outline.front_matter is not None:
        front_matter = {
            "title": outline.front_matter.title,
            "page_start": outline.front_matter.page_start,
            "page_end": outline.front_matter.page_end,
        }

    payload: dict[str, Any] = {
        "course_id": course_id,
        "document": outline.document,
        "page_index_base": outline.page_index_base,
        "page_count": outline.page_count,
        "front_matter": front_matter,
        "units": [
            {
                "id": unit.id,
                "title": unit.title,
                "page_start": unit.page_start,
                "page_end": unit.page_end,
                "sections": [
                    {
                        "title": section.title,
                        "page_start": section.page_start,
                        "page_end": section.page_end,
                    }
                    for section in unit.sections
                ],
            }
            for unit in outline.units
        ],
    }
    if outline_source is not None:
        payload["outline_source"] = outline_source
    if outline_granularity is not None:
        payload["outline_granularity"] = outline_granularity
    if outline_quality is not None:
        payload["outline_quality"] = outline_quality
    return payload


def get_course_outline(session: Session, course_id: str) -> dict[str, Any] | None:
    """Return outline JSON for a course, or None if course unknown / no outline available."""
    course = session.get(Course, course_id)
    outline, source = resolve_course_outline(session, course_id)
    if outline is None:
        return None
    granularity = _outline_granularity(course, source)
    quality = _outline_quality(course, source)
    if source == "auto_stub" and quality is None:
        quality = outline_quality_score(outline, "page_stub", is_auto_stub=True)
    payload = serialize_course_outline(
        outline,
        course_id,
        outline_source=source,
        outline_granularity=granularity,
        outline_quality=quality,
    )
    if course and course.outline_data and course.outline_data.get("outline_extraction_method"):
        payload["outline_extraction_method"] = course.outline_data["outline_extraction_method"]
    return payload


def save_course_outline(session: Session, course_id: str, outline_data: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist uploaded outline JSON for a course."""
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course not found: {course_id}")

    outline = parse_outline_data(outline_data)
    if not outline.units:
        raise ValueError("Outline must include at least one unit")

    stored = dict(outline_data)
    stored["outline_source"] = "uploaded"
    course.outline_data = stored
    session.commit()
    return serialize_course_outline(outline, course_id, outline_source="uploaded")


def persist_extracted_outline(
    session: Session,
    course_id: str,
    outline: DocumentOutline,
    *,
    outline_granularity: OutlineGranularity | None = None,
    outline_quality: OutlineQuality | None = None,
) -> None:
    """Store extracted outline unless an uploaded outline is already locked."""
    course = session.get(Course, course_id)
    if course is None:
        return
    if _stored_outline_source(course) == "uploaded":
        return
    course.outline_data = outline_to_storage_dict(
        outline,
        "extracted",
        outline_granularity=outline_granularity,
        outline_quality=outline_quality,
    )
    session.flush()


def maybe_extract_outline_on_notes_ingest(
    session: Session,
    *,
    course_id: str,
    filename: str,
    file_path: Path,
    pages: list,
) -> dict[str, Any] | None:
    """
    Extract TOC from notes PDF during ingest.
    Skips fixture-backed courses and courses with uploaded outlines.
    """
    if outline_path_for_course(course_id) is not None:
        return None

    course = session.get(Course, course_id)
    if course and _stored_outline_source(course) == "uploaded":
        return None

    outline, granularity, quality = extract_outline_from_pdf(file_path, pages=pages)
    if outline is None:
        return None

    outline.document = filename
    outline.course = course_id
    annotate_pages_with_outline(pages, outline)
    persist_extracted_outline(
        session,
        course_id,
        outline,
        outline_granularity=granularity,
        outline_quality=quality,
    )
    return outline_summary(outline, "extracted")


def rebuild_course_outline(session: Session, course_id: str) -> dict[str, Any]:
    """Re-extract outline from existing notes PDFs without re-upload."""
    if outline_path_for_course(course_id) is not None:
        raise ValueError("Fixture-backed courses cannot be rebuilt")

    course = session.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course not found: {course_id}")
    if _stored_outline_source(course) == "uploaded":
        raise ValueError("Cannot rebuild: uploaded outline is locked")

    notes_docs = _fetch_notes_documents(session, course_id)
    if not notes_docs:
        raise ValueError("No notes documents to extract outline from")

    for document in notes_docs:
        if not document.file_path:
            continue
        file_path = Path(document.file_path)
        if not file_path.is_file():
            continue
        extraction = extract_pdf(file_path)
        outline, granularity, quality = extract_outline_from_pdf(file_path, pages=extraction.pages)
        if outline is None:
            continue
        outline.document = document.filename
        outline.course = course_id
        course.outline_data = outline_to_storage_dict(
            outline,
            "extracted",
            outline_granularity=granularity,
            outline_quality=quality,
        )
        session.commit()
        return serialize_course_outline(
            outline,
            course_id,
            outline_source="extracted",
            outline_granularity=granularity,
            outline_quality=quality,
        )

    raise ValueError("Could not extract outline from notes PDFs (no bookmarks or text TOC found)")


def notes_fallback_label(session: Session, course_id: str) -> str:
    """Filename stem of primary notes doc, or 'General'."""
    notes_docs = _fetch_notes_documents(session, course_id)
    if notes_docs:
        return Path(notes_docs[0].filename).stem
    return "General"
