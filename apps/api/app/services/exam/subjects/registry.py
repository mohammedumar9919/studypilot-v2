"""Subject pack registry — resolve course_id to parse/taxonomy/golden behavior (SP-064a)."""

from __future__ import annotations

from app.services.exam.subjects.base import SubjectPack
from app.services.exam.subjects.chemistry import ChemistryPack
from app.services.exam.subjects.generic import GenericPack

_GENERIC = GenericPack()
_CHEMISTRY = ChemistryPack()


def get_pack(course_id: str) -> SubjectPack:
    """Return the subject pack for analytics/taxonomy; parse routing may still use filename heuristics."""
    if ChemistryPack.matches_course_id(course_id):
        return _CHEMISTRY
    return _GENERIC


def resolve_parse_pack(
    *,
    course_id: str,
    filename: str,
    sample_text: str = "",
) -> SubjectPack:
    """Pack for ingest-time PYQ parse (filename/sample heuristics may override course_id)."""
    if _CHEMISTRY.should_use_custom_parse(
        course_id=course_id,
        filename=filename,
        sample_text=sample_text,
    ):
        return _CHEMISTRY
    return _GENERIC
