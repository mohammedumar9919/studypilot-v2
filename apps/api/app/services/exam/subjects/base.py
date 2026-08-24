"""Subject pack protocol — parse routing, taxonomy, golden reference (SP-064a)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.models import ExamQuestion
    from app.services.pdf_extract import DocumentOutline, PageText


@runtime_checkable
class SubjectPack(Protocol):
    """Per-course exam behavior: custom parse, question classification, golden validate."""

    @property
    def pack_id(self) -> str:
        """Stable pack identifier (e.g. chemistry, generic)."""
        ...

    def should_use_custom_parse(
        self,
        *,
        course_id: str,
        filename: str,
        sample_text: str = "",
    ) -> bool:
        """True when this pack's ingest-time parser should run instead of generic PYQ."""
        ...

    def parse_pages(
        self,
        *,
        pages: list[PageText],
        document_id: Any,
        course_id: str,
        filename: str,
        outline: DocumentOutline | None,
    ) -> list[Any] | None:
        """Return exam question drafts when custom parse applies; None to fall through."""
        ...

    def classify_question(
        self,
        question: ExamQuestion,
        *,
        session: Any = None,
    ) -> tuple[str, str, str]:
        """Return (unit, topic, subtopic) for analytics and reference metrics."""
        ...

    def golden_path(self) -> Path | None:
        """Optional golden reference JSON for validate CLI; None when not applicable."""
        ...
