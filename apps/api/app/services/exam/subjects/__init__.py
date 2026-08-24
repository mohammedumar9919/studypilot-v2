"""Pluggable subject packs for exam parse, taxonomy, and golden validation (SP-064a)."""

from app.services.exam.subjects.base import SubjectPack

__all__ = ["SubjectPack", "get_pack"]


def __getattr__(name: str):
    if name == "get_pack":
        from app.services.exam.subjects.registry import get_pack

        return get_pack
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
