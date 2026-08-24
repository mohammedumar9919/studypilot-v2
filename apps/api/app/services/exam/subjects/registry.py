"""Subject pack registry — resolve course_id to parse/taxonomy/golden behavior (SP-064a)."""

from __future__ import annotations

from pathlib import Path

from app.services.exam.subjects.base import SubjectPack
from app.services.exam.subjects.chemistry import ChemistryPack
from app.services.exam.subjects.generic import GenericPack
from app.services.exam.subjects.ppl import PplPack

_GENERIC = GenericPack()
_CHEMISTRY = ChemistryPack()
_PPL = PplPack()


def get_pack(course_id: str) -> SubjectPack:
    """Return the subject pack for analytics/taxonomy; parse routing may still use filename heuristics."""
    if ChemistryPack.matches_course_id(course_id):
        return _CHEMISTRY
    if PplPack.matches_course_id(course_id):
        return _PPL
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
    if _PPL.should_use_custom_parse(
        course_id=course_id,
        filename=filename,
        sample_text=sample_text,
    ):
        return _PPL
    return _GENERIC


def pack_pyq_seed_path(course_id: str) -> Path | None:
    """Optional PYQ seed YAML path from the registered subject pack."""
    getter = getattr(get_pack(course_id), "pyq_seed_path", None)
    if not callable(getter):
        return None
    path = getter()
    return path if path is not None and path.is_file() else None


def pack_outline_fixture_path(course_id: str) -> Path | None:
    """Optional outline fixture YAML path from the registered subject pack."""
    getter = getattr(get_pack(course_id), "outline_fixture_path", None)
    if not callable(getter):
        return None
    path = getter()
    return path if path is not None and path.is_file() else None
