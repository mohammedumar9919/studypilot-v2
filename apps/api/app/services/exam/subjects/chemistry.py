"""OU Engineering Chemistry subject pack — wraps ou_chemistry + chemistry_taxonomy (SP-064a)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.services.exam.ou_chemistry import is_ou_chemistry_source

if TYPE_CHECKING:
    from app.models import ExamQuestion
    from app.services.pdf_extract import DocumentOutline, PageText

_CHEMISTRY_COURSE_IDS = frozenset({"chemistry", "chem"})


class ChemistryPack:
    """First registered pack; zero behavior regression for chemistry UAT."""

    pack_id = "chemistry"

    def should_use_custom_parse(
        self,
        *,
        course_id: str,
        filename: str,
        sample_text: str = "",
    ) -> bool:
        return is_ou_chemistry_source(
            course_id=course_id,
            filename=filename,
            sample_text=sample_text,
        )

    def parse_pages(
        self,
        *,
        pages: list[PageText],
        document_id: Any,
        course_id: str,
        filename: str,
        outline: DocumentOutline | None,
    ) -> list[Any] | None:
        del document_id, course_id, filename
        from app.services.exam.pyq_parser import _parse_ou_chemistry_bundle
        from app.services.exam.topic_frequency import _build_keyword_patterns

        patterns = _build_keyword_patterns(outline) if outline else None
        return _parse_ou_chemistry_bundle(pages, outline=outline, patterns=patterns)

    def classify_question(
        self,
        question: ExamQuestion,
        *,
        session: Any = None,
    ) -> tuple[str, str, str]:
        del session
        from app.services.exam.chemistry_taxonomy import classify_chemistry_question

        return classify_chemistry_question(question)

    def golden_path(self) -> Path | None:
        from app.services.exam.reference_report import DEFAULT_GOLDEN_PATH

        return DEFAULT_GOLDEN_PATH if DEFAULT_GOLDEN_PATH.is_file() else None

    @staticmethod
    def matches_course_id(course_id: str) -> bool:
        return course_id.strip().lower() in _CHEMISTRY_COURSE_IDS
