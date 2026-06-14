"""Course structure — units/parts/subtopics tree, paste/syllabus import, confirm (SP-053a)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Course,
    CoursePart,
    CourseSubtopic,
    CourseUnit,
    Document,
    DocumentPartLink,
    DocumentSubtopicLink,
    DocumentUnitLink,
)
from app.services.course_documents import VISIBLE_STATUSES
from app.services.course_outline import find_syllabus_document
from app.services.rag.retrieve import STUDY_DOC_KINDS


def _split_comma_topics(line: str) -> list[str]:
    return [item.strip() for item in line.split(",") if item.strip()]


def _parse_unit_block(unit_title: str, body_lines: list[tuple[int, str]]) -> dict[str, Any]:
    has_parts = any(indent >= 4 for indent, _ in body_lines)

    if has_parts:
        parts: list[dict[str, Any]] = []
        current_part: dict[str, Any] | None = None
        for indent, content in body_lines:
            if indent == 2:
                if current_part is not None:
                    parts.append(current_part)
                current_part = {"title": content, "subtopics": []}
            elif indent >= 4:
                if current_part is None:
                    raise ValueError(f"Subtopic before part in unit: {unit_title}")
                current_part["subtopics"].extend(_split_comma_topics(content))
            else:
                raise ValueError(f"Invalid indent {indent} in unit with parts: {unit_title}")
        if current_part is not None:
            parts.append(current_part)
        if not parts:
            raise ValueError(f"No parts found in unit: {unit_title}")
        return {"title": unit_title, "parts": parts}

    subtopics: list[str] = []
    for indent, content in body_lines:
        if indent >= 2:
            if indent >= 4:
                raise ValueError(f"Unexpected deep indent in flat unit: {unit_title}")
            subtopics.extend(_split_comma_topics(content))
        else:
            raise ValueError(f"Invalid indent in flat unit: {unit_title}")
    return {"title": unit_title, "subtopics": subtopics}


def parse_pasted_structure(text: str) -> list[dict[str, Any]]:
    """Parse pasted outline: indent 0=unit, 2=part or flat subtopic, 4=topic/comma line."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    unit_blocks: list[tuple[str, list[tuple[int, str]]]] = []
    current_title: str | None = None
    current_body: list[tuple[int, str]] = []

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip()
        indent = len(raw_line) - len(stripped)
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
            indent = max(indent, 2)

        if indent == 0:
            if current_title is not None:
                unit_blocks.append((current_title, current_body))
            current_title = stripped.strip()
            current_body = []
            continue

        if current_title is None:
            raise ValueError("Subtopic line before any unit title")
        current_body.append((indent, stripped.strip()))

    if current_title is not None:
        unit_blocks.append((current_title, current_body))

    if not unit_blocks:
        raise ValueError("No units found in pasted text")

    return [_parse_unit_block(title, body) for title, body in unit_blocks]


def _preview_units_from_parser(raw_units: list[Any]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for unit in raw_units:
        if isinstance(unit, dict):
            title = str(unit.get("unit_title") or unit.get("title") or "").strip()
            raw_parts = unit.get("parts")
            raw_subtopics = unit.get("subtopic_titles") or unit.get("subtopics") or []
        else:
            title = str(getattr(unit, "unit_title", "") or getattr(unit, "title", "")).strip()
            raw_parts = getattr(unit, "parts", None)
            raw_subtopics = getattr(unit, "subtopic_titles", None) or getattr(unit, "subtopics", [])

        if not title:
            continue

        if raw_parts:
            parts: list[dict[str, Any]] = []
            for raw_part in raw_parts:
                if isinstance(raw_part, dict):
                    part_title = str(
                        raw_part.get("part_title") or raw_part.get("title") or ""
                    ).strip()
                    part_subtopics = (
                        raw_part.get("subtopic_titles")
                        or raw_part.get("subtopics")
                        or []
                    )
                else:
                    part_title = str(
                        getattr(raw_part, "part_title", "") or getattr(raw_part, "title", "")
                    ).strip()
                    part_subtopics = (
                        getattr(raw_part, "subtopic_titles", None)
                        or getattr(raw_part, "subtopics", [])
                    )
                if not part_title:
                    continue
                subtopics = [str(item).strip() for item in part_subtopics if str(item).strip()]
                parts.append({"title": part_title, "subtopics": subtopics})
            if parts:
                preview.append({"title": title, "parts": parts})
                continue

        subtopics = [str(item).strip() for item in raw_subtopics if str(item).strip()]
        preview.append({"title": title, "subtopics": subtopics})

    if not preview:
        raise ValueError("syllabus_parse_failed")
    return preview


def _parse_syllabus_pdf(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Call Agent B syllabus structure parser; returns preview units and optional warning."""
    from app.services import pdf_extract

    parser = getattr(pdf_extract, "parse_syllabus_course_structure", None)
    if parser is not None:
        result = parser(path)
        if isinstance(result, tuple) and len(result) == 2:
            raw_units, warning = result
        else:
            raw_units, warning = result, None
        return _preview_units_from_parser(raw_units), warning

    extraction = pdf_extract.extract_pdf(path)
    raw_units = pdf_extract._parse_engineering_syllabus_structure(extraction.pages)
    if not raw_units:
        raise ValueError("syllabus_parse_failed")
    warning = None
    if len(raw_units) < 2:
        warning = "Parsed fewer than two units from syllabus"
    return _preview_units_from_parser(raw_units), warning


def _resolve_syllabus_document(
    session: Session,
    course_id: str,
    document_id: str | None,
) -> Document:
    if document_id:
        try:
            parsed_id = uuid.UUID(document_id)
        except ValueError as exc:
            raise ValueError(f"Invalid document_id UUID: {document_id}") from exc
        document = session.get(Document, parsed_id)
        if document is None or document.course_id != course_id:
            raise ValueError(f"Document not found for course: {document_id}")
        if document.status != "ready" or not document.file_path:
            raise ValueError("Syllabus document is not ready")
        if not Path(document.file_path).is_file():
            raise ValueError("Syllabus document file missing on disk")
        return document

    document = find_syllabus_document(session, course_id)
    if document is None:
        raise ValueError("syllabus_document_not_found")
    return document


def import_pasted_structure(session: Session, course_id: str, text: str) -> dict[str, Any] | None:
    """Preview pasted structure without persisting."""
    if session.get(Course, course_id) is None:
        return None
    units = parse_pasted_structure(text)
    return {"preview": True, "units": units}


def import_syllabus_structure(
    session: Session,
    course_id: str,
    *,
    document_id: str | None = None,
) -> dict[str, Any] | None:
    """Preview syllabus-derived structure without persisting."""
    if session.get(Course, course_id) is None:
        return None
    document = _resolve_syllabus_document(session, course_id, document_id)
    units, warning = _parse_syllabus_pdf(Path(document.file_path))
    payload: dict[str, Any] = {"preview": True, "units": units}
    if warning:
        payload["parse_warning"] = warning
    return payload


def _validate_subtopic_titles(raw_subtopics: Any, field_path: str) -> list[str]:
    if raw_subtopics is None:
        raw_subtopics = []
    if not isinstance(raw_subtopics, list):
        raise ValueError(f"{field_path} must be a list")
    return [str(item).strip() for item in raw_subtopics if str(item).strip()]


def _validate_confirm_parts(raw_parts: Any, unit_path: str) -> list[dict[str, Any]]:
    if not isinstance(raw_parts, list) or not raw_parts:
        raise ValueError(f"{unit_path}.parts must be a non-empty list")
    validated: list[dict[str, Any]] = []
    for part_index, raw_part in enumerate(raw_parts):
        part_path = f"{unit_path}.parts[{part_index}]"
        if not isinstance(raw_part, dict):
            raise ValueError(f"{part_path} must be an object")
        title = str(raw_part.get("title", "")).strip()
        if not title:
            raise ValueError(f"{part_path}.title must not be empty")
        subtopics = _validate_subtopic_titles(raw_part.get("subtopics"), f"{part_path}.subtopics")
        validated.append({"title": title, "subtopics": subtopics})
    return validated


def _validate_confirm_units(raw_units: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("units must be a non-empty list")

    validated: list[dict[str, Any]] = []
    for index, raw_unit in enumerate(raw_units):
        unit_path = f"units[{index}]"
        if not isinstance(raw_unit, dict):
            raise ValueError(f"{unit_path} must be an object")
        title = str(raw_unit.get("title", "")).strip()
        if not title:
            raise ValueError(f"{unit_path}.title must not be empty")

        raw_parts = raw_unit.get("parts")
        if raw_parts is not None:
            parts = _validate_confirm_parts(raw_parts, unit_path)
            validated.append({"title": title, "parts": parts})
            continue

        subtopics = _validate_subtopic_titles(raw_unit.get("subtopics"), f"{unit_path}.subtopics")
        validated.append({"title": title, "subtopics": subtopics})
    return validated


def _delete_course_structure(session: Session, course_id: str) -> None:
    session.execute(delete(CourseUnit).where(CourseUnit.course_id == course_id))


def confirm_course_structure(
    session: Session,
    course_id: str,
    units_payload: Any,
) -> dict[str, Any] | None:
    """Replace course structure and promote course to organized mode."""
    course = session.get(Course, course_id)
    if course is None:
        return None

    units = _validate_confirm_units(units_payload)
    _delete_course_structure(session, course_id)

    for unit_index, unit_data in enumerate(units):
        unit = CourseUnit(
            course_id=course_id,
            title=unit_data["title"],
            sort_order=unit_index,
        )
        session.add(unit)
        session.flush()

        if unit_data.get("parts"):
            for part_index, part_data in enumerate(unit_data["parts"]):
                part = CoursePart(
                    unit_id=unit.id,
                    title=part_data["title"],
                    sort_order=part_index,
                )
                session.add(part)
                session.flush()
                for subtopic_index, subtopic_title in enumerate(part_data["subtopics"]):
                    session.add(
                        CourseSubtopic(
                            unit_id=unit.id,
                            part_id=part.id,
                            title=subtopic_title,
                            sort_order=subtopic_index,
                        )
                    )
            continue

        for subtopic_index, subtopic_title in enumerate(unit_data.get("subtopics", [])):
            session.add(
                CourseSubtopic(
                    unit_id=unit.id,
                    part_id=None,
                    title=subtopic_title,
                    sort_order=subtopic_index,
                )
            )

    course.structure_mode = "organized"
    session.commit()
    return get_course_structure(session, course_id)


def _serialize_subtopic(subtopic: CourseSubtopic) -> dict[str, Any]:
    document_ids = sorted({str(link.document_id) for link in subtopic.document_links})
    return {
        "id": str(subtopic.id),
        "title": subtopic.title,
        "sort_order": subtopic.sort_order,
        "document_ids": document_ids,
    }


def _serialize_part(part: CoursePart) -> dict[str, Any]:
    document_ids = sorted({str(link.document_id) for link in part.document_links})
    return {
        "id": str(part.id),
        "title": part.title,
        "sort_order": part.sort_order,
        "subtopics": [
            _serialize_subtopic(subtopic)
            for subtopic in sorted(part.subtopics, key=lambda item: (item.sort_order, item.title))
        ],
        "document_ids": document_ids,
    }


def _serialize_unit(unit: CourseUnit) -> dict[str, Any]:
    document_ids = sorted({str(link.document_id) for link in unit.document_links})
    sorted_parts = sorted(unit.parts, key=lambda item: (item.sort_order, item.title))
    unit_subtopics = sorted(
        (subtopic for subtopic in unit.subtopics if subtopic.part_id is None),
        key=lambda item: (item.sort_order, item.title),
    )

    payload: dict[str, Any] = {
        "id": str(unit.id),
        "title": unit.title,
        "sort_order": unit.sort_order,
        "document_ids": document_ids,
    }
    if sorted_parts:
        payload["parts"] = [_serialize_part(part) for part in sorted_parts]
    else:
        payload["subtopics"] = [_serialize_subtopic(subtopic) for subtopic in unit_subtopics]
    return payload


def get_course_structure(session: Session, course_id: str) -> dict[str, Any] | None:
    """Return persisted course structure tree, or None if course unknown."""
    if session.get(Course, course_id) is None:
        return None

    stmt = (
        select(CourseUnit)
        .where(CourseUnit.course_id == course_id)
        .options(
            selectinload(CourseUnit.parts)
            .selectinload(CoursePart.subtopics)
            .selectinload(CourseSubtopic.document_links),
            selectinload(CourseUnit.parts).selectinload(CoursePart.document_links),
            selectinload(CourseUnit.subtopics).selectinload(CourseSubtopic.document_links),
            selectinload(CourseUnit.document_links),
        )
        .order_by(CourseUnit.sort_order, CourseUnit.title)
    )
    units = list(session.scalars(stmt).all())
    return {
        "course_id": course_id,
        "units": [_serialize_unit(unit) for unit in units],
    }


def _parse_document_id_list(raw_ids: Any, *, field_name: str) -> list[uuid.UUID]:
    if raw_ids is None:
        raw_ids = []
    if not isinstance(raw_ids, list):
        raise ValueError(f"{field_name} must be a list")
    parsed: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            parsed.append(uuid.UUID(str(raw_id)))
        except ValueError as exc:
            raise ValueError(f"Invalid {field_name} UUID: {raw_id}") from exc
    return parsed


def _validate_assignment_documents(
    session: Session,
    course_id: str,
    document_ids: list[uuid.UUID],
) -> None:
    for doc_id in document_ids:
        document = session.get(Document, doc_id)
        if document is None or document.course_id != course_id:
            raise ValueError(f"Document not found for course: {doc_id}")
        if document.status not in VISIBLE_STATUSES:
            raise ValueError(f"Document status not usable for assignment: {doc_id}")
        if document.doc_kind not in STUDY_DOC_KINDS:
            raise ValueError(f"Document doc_kind not allowed for structure assignment: {doc_id}")


def assign_unit_documents(
    session: Session,
    course_id: str,
    unit_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> dict[str, Any] | None:
    """Replace M2M document links for a course unit."""
    unit = session.get(CourseUnit, unit_id)
    if unit is None or unit.course_id != course_id:
        return None
    _validate_assignment_documents(session, course_id, document_ids)
    session.execute(delete(DocumentUnitLink).where(DocumentUnitLink.unit_id == unit_id))
    for doc_id in document_ids:
        session.add(DocumentUnitLink(document_id=doc_id, unit_id=unit_id))
    session.commit()
    result = get_course_structure(session, course_id)
    assert result is not None
    return result


def assign_part_documents(
    session: Session,
    course_id: str,
    part_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> dict[str, Any] | None:
    """Replace M2M document links for a course part."""
    part = session.get(CoursePart, part_id)
    if part is None or part.unit.course_id != course_id:
        return None
    _validate_assignment_documents(session, course_id, document_ids)
    session.execute(delete(DocumentPartLink).where(DocumentPartLink.part_id == part_id))
    for doc_id in document_ids:
        session.add(DocumentPartLink(document_id=doc_id, part_id=part_id))
    session.commit()
    result = get_course_structure(session, course_id)
    assert result is not None
    return result


def assign_subtopic_documents(
    session: Session,
    course_id: str,
    subtopic_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> dict[str, Any] | None:
    """Replace M2M document links for a course subtopic."""
    subtopic = session.get(CourseSubtopic, subtopic_id)
    if subtopic is None or subtopic.unit.course_id != course_id:
        return None
    _validate_assignment_documents(session, course_id, document_ids)
    session.execute(
        delete(DocumentSubtopicLink).where(DocumentSubtopicLink.subtopic_id == subtopic_id)
    )
    for doc_id in document_ids:
        session.add(DocumentSubtopicLink(document_id=doc_id, subtopic_id=subtopic_id))
    session.commit()
    result = get_course_structure(session, course_id)
    assert result is not None
    return result


def _load_unit_with_links(session: Session, unit_id: uuid.UUID) -> CourseUnit | None:
    stmt = (
        select(CourseUnit)
        .where(CourseUnit.id == unit_id)
        .options(
            selectinload(CourseUnit.document_links),
            selectinload(CourseUnit.parts)
            .selectinload(CoursePart.document_links),
            selectinload(CourseUnit.parts)
            .selectinload(CoursePart.subtopics)
            .selectinload(CourseSubtopic.document_links),
            selectinload(CourseUnit.subtopics).selectinload(CourseSubtopic.document_links),
        )
    )
    return session.scalars(stmt).first()


def _load_part_with_links(session: Session, part_id: uuid.UUID) -> CoursePart | None:
    stmt = (
        select(CoursePart)
        .where(CoursePart.id == part_id)
        .options(
            selectinload(CoursePart.document_links),
            selectinload(CoursePart.unit).selectinload(CourseUnit.document_links),
            selectinload(CoursePart.subtopics).selectinload(CourseSubtopic.document_links),
        )
    )
    return session.scalars(stmt).first()


def _load_subtopic_with_links(session: Session, subtopic_id: uuid.UUID) -> CourseSubtopic | None:
    stmt = (
        select(CourseSubtopic)
        .where(CourseSubtopic.id == subtopic_id)
        .options(
            selectinload(CourseSubtopic.document_links),
            selectinload(CourseSubtopic.part).selectinload(CoursePart.document_links),
            selectinload(CourseSubtopic.unit).selectinload(CourseUnit.document_links),
        )
    )
    return session.scalars(stmt).first()


def _collect_document_ids_for_units(
    session: Session,
    unit_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    doc_ids: set[uuid.UUID] = set()
    for unit_id in unit_ids:
        unit = _load_unit_with_links(session, unit_id)
        if unit is None:
            continue
        doc_ids.update(link.document_id for link in unit.document_links)
        for part in unit.parts:
            doc_ids.update(link.document_id for link in part.document_links)
            for subtopic in part.subtopics:
                doc_ids.update(link.document_id for link in subtopic.document_links)
        for subtopic in unit.subtopics:
            if subtopic.part_id is None:
                doc_ids.update(link.document_id for link in subtopic.document_links)
    return doc_ids


def _collect_document_ids_for_parts(
    session: Session,
    part_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    doc_ids: set[uuid.UUID] = set()
    for part_id in part_ids:
        part = _load_part_with_links(session, part_id)
        if part is None:
            continue
        doc_ids.update(link.document_id for link in part.document_links)
        doc_ids.update(link.document_id for link in part.unit.document_links)
        for subtopic in part.subtopics:
            doc_ids.update(link.document_id for link in subtopic.document_links)
    return doc_ids


def _collect_document_ids_for_subtopics(
    session: Session,
    subtopic_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    doc_ids: set[uuid.UUID] = set()
    for subtopic_id in subtopic_ids:
        subtopic = _load_subtopic_with_links(session, subtopic_id)
        if subtopic is None:
            continue
        doc_ids.update(link.document_id for link in subtopic.document_links)
        if subtopic.part is not None:
            doc_ids.update(link.document_id for link in subtopic.part.document_links)
        doc_ids.update(link.document_id for link in subtopic.unit.document_links)
    return doc_ids


def expand_structure_scope_to_document_ids(
    session: Session,
    *,
    unit_ids: list[uuid.UUID] | None = None,
    part_ids: list[uuid.UUID] | None = None,
    subtopic_ids: list[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    """Expand structure node ids to document ids with parent/child inheritance."""
    doc_ids: set[uuid.UUID] = set()
    if unit_ids:
        doc_ids.update(_collect_document_ids_for_units(session, unit_ids))
    if part_ids:
        doc_ids.update(_collect_document_ids_for_parts(session, part_ids))
    if subtopic_ids:
        doc_ids.update(_collect_document_ids_for_subtopics(session, subtopic_ids))
    return sorted(doc_ids)


def validate_structure_scope_ids(
    session: Session,
    *,
    course_id: str,
    unit_ids: list[str] | None,
    part_ids: list[str] | None,
    subtopic_ids: list[str] | None,
    preset: str,
) -> list[uuid.UUID]:
    """Parse structure scope ids and expand to document_ids for retrieval. Raises ValueError (400)."""
    from app.services.study_topics import STUDY_PRESETS

    if preset not in STUDY_PRESETS:
        raise ValueError(f"structure scope not allowed for preset {preset}")

    has_unit = unit_ids is not None
    has_part = part_ids is not None
    has_subtopic = subtopic_ids is not None
    if not has_unit and not has_part and not has_subtopic:
        return []

    if has_unit and not unit_ids:
        raise ValueError("unit_ids must not be empty when provided")
    if has_part and not part_ids:
        raise ValueError("part_ids must not be empty when provided")
    if has_subtopic and not subtopic_ids:
        raise ValueError("subtopic_ids must not be empty when provided")

    parsed_units = _parse_document_id_list(unit_ids or [], field_name="unit_ids")
    parsed_parts = _parse_document_id_list(part_ids or [], field_name="part_ids")
    parsed_subtopics = _parse_document_id_list(subtopic_ids or [], field_name="subtopic_ids")

    for unit_id in parsed_units:
        unit = session.get(CourseUnit, unit_id)
        if unit is None or unit.course_id != course_id:
            raise ValueError(f"Course unit not found for course: {unit_id}")

    for part_id in parsed_parts:
        part = session.get(CoursePart, part_id)
        if part is None or part.unit.course_id != course_id:
            raise ValueError(f"Course part not found for course: {part_id}")

    for subtopic_id in parsed_subtopics:
        subtopic = session.get(CourseSubtopic, subtopic_id)
        if subtopic is None or subtopic.unit.course_id != course_id:
            raise ValueError(f"Course subtopic not found for course: {subtopic_id}")

    document_ids = expand_structure_scope_to_document_ids(
        session,
        unit_ids=parsed_units or None,
        part_ids=parsed_parts or None,
        subtopic_ids=parsed_subtopics or None,
    )
    if not document_ids:
        raise ValueError("structure scope matched no assigned documents")
    return document_ids
