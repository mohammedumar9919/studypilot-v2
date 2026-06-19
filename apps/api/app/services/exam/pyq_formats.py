"""Format detection helpers for PYQ OCR text (SP-042c)."""

from __future__ import annotations

import re

from app.services.exam.topic_frequency import _READABLE_CHAR_THRESHOLD

PaperFormat = str  # part_ab | compulsory_q1 | continuation | skip

_WATERMARK = re.compile(r"ODDASIF|Download ISL Student", re.IGNORECASE)
_PART_LINE = re.compile(r"^\s*PART\s*[-\s—–]*\s*([AB])\b", re.IGNORECASE | re.MULTILINE)
_COMPULSORY_NOTE = re.compile(r"first question is compulsory", re.IGNORECASE)
_COMPULSORY_Q1 = re.compile(r"^\s*1\.\s*([a-g])\)\s+", re.IGNORECASE | re.MULTILINE)
_CONT_START = re.compile(
    r"^\s*(?:\d+\s*)?(?:1[1-7]|[1-9])\s*([a-c])\)\s+",
    re.IGNORECASE | re.MULTILINE,
)
_CODE_NO = re.compile(r"Code\s*No\.?\s*[:\s]*[\w/-]+", re.IGNORECASE)


def strip_watermarks(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not _WATERMARK.search(ln)]
    return "\n".join(lines)


def has_part_sections(text: str) -> bool:
    """True when a standalone PART-A / PART-B header exists (not Note-line only)."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\s*Note\b", stripped, re.IGNORECASE):
            continue
        if _PART_LINE.match(stripped):
            return True
    return False


def is_compulsory(text: str) -> bool:
    if _COMPULSORY_NOTE.search(text):
        return True
    return bool(_COMPULSORY_Q1.search(text) and re.search(r"^\s*[2-7]\.\s*[a-c]\)", text, re.I | re.M))


def is_continuation(text: str) -> bool:
    if has_part_sections(text):
        return False
    if is_compulsory(text):
        return False
    sample = text.strip()[:400]
    if _CONT_START.search(sample):
        return True
    if _CODE_NO.search(sample) and not re.search(r"FACULTY OF|Subject:", sample, re.I):
        return _CONT_START.search(text)
    return False


def detect_format(text: str) -> PaperFormat:
    cleaned = strip_watermarks(text)
    if is_continuation(cleaned):
        return "continuation"
    if len(cleaned.strip()) < _READABLE_CHAR_THRESHOLD:
        return "skip"
    if is_compulsory(cleaned):
        return "compulsory_q1"
    if has_part_sections(cleaned):
        return "part_ab"
    if re.search(r"^\s*[1-9]\d?\s*[\.\)]\s+[A-Za-z]", cleaned, re.MULTILINE):
        return "part_ab"
    return "skip"
