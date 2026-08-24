"""Default subject pack — structure-first taxonomy with parser fallback (SP-064a/064b)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import ExamQuestion
    from app.services.pdf_extract import DocumentOutline, PageText

_STRUCTURE_CACHE: dict[tuple[int, str], dict[str, Any] | None] = {}


def _structure_for_course(session: Session, course_id: str) -> dict[str, Any] | None:
    cache_key = (id(session), course_id)
    if cache_key not in _STRUCTURE_CACHE:
        from app.services.course_structure import get_course_structure

        _STRUCTURE_CACHE[cache_key] = get_course_structure(session, course_id)
    return _STRUCTURE_CACHE[cache_key]


class GenericPack:
    """Universal pack: mapped structure match, then parser unit/section hints."""

    pack_id = "generic"

    def should_use_custom_parse(
        self,
        *,
        course_id: str,
        filename: str,
        sample_text: str = "",
    ) -> bool:
        del course_id, filename, sample_text
        return False

    def parse_pages(
        self,
        *,
        pages: list[PageText],
        document_id: Any,
        course_id: str,
        filename: str,
        outline: DocumentOutline | None,
    ) -> list[Any] | None:
        del pages, document_id, course_id, filename, outline
        return None

    def classify_question(
        self,
        question: ExamQuestion,
        *,
        session: Session | None = None,
    ) -> tuple[str, str, str]:
        prompt = (question.prompt_text or "").strip()
        extra_terms: list[str] = []
        if question.unit:
            extra_terms.append(question.unit)
        if question.section_title:
            extra_terms.append(question.section_title)

        if session is not None:
            structure = _structure_for_course(session, question.course_id)
            if structure and structure.get("units"):
                from app.services.exam.analytics_structure import match_prompt_to_structure

                matched = match_prompt_to_structure(
                    prompt,
                    structure,
                    extra_terms=extra_terms or None,
                )
                if matched is not None:
                    return matched

        return self._parser_fallback(question)

    @staticmethod
    def _parser_fallback(question: ExamQuestion) -> tuple[str, str, str]:
        from app.services.exam.reference_report import _normalize_unit

        unit = _normalize_unit(question.unit)
        section = (question.section_title or "").strip()
        if unit or section:
            resolved_unit = unit or "Unmapped"
            topic = section or resolved_unit or "Unclassified"
            subtopic = section or topic
            return resolved_unit, topic, subtopic
        return "Unmapped", "Unmapped", "Unmapped"

    def golden_path(self) -> Path | None:
        return None
