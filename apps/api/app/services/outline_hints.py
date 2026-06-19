"""Build retrieval / heatmap keyword hints from a course outline (no LLM)."""

from __future__ import annotations

import re

from app.services.pdf_extract import DocumentOutline

_MIN_PHRASE_LEN = 4


def build_unit_phrases_from_outline(outline: DocumentOutline) -> dict[str, tuple[str, ...]]:
    """Unit id → search phrases derived from unit/section titles."""
    phrases: dict[str, tuple[str, ...]] = {}
    for unit in outline.units:
        collected: list[str] = []
        unit_title = unit.title.lower().strip()
        if unit_title:
            collected.append(unit_title)
        for section in unit.sections:
            title_lower = section.title.lower().strip()
            if title_lower:
                collected.append(title_lower)
            for token in re.split(r"[^a-z0-9]+", title_lower):
                if len(token) >= _MIN_PHRASE_LEN:
                    collected.append(token)
        seen: set[str] = set()
        unique: list[str] = []
        for phrase in sorted({p for p in collected if p and len(p) >= _MIN_PHRASE_LEN}, key=len, reverse=True):
            if phrase not in seen:
                seen.add(phrase)
                unique.append(phrase)
        if unique:
            phrases[unit.id] = tuple(unique)
    return phrases


def build_unit_terms_from_outline(outline: DocumentOutline) -> dict[str, frozenset[str]]:
    """Unit id → token set from section titles (≥5 chars)."""
    terms: dict[str, frozenset[str]] = {}
    for unit in outline.units:
        tokens: set[str] = set()
        for section in unit.sections:
            for token in re.split(r"[^a-z0-9]+", section.title.lower()):
                if len(token) >= 5:
                    tokens.add(token)
        if tokens:
            terms[unit.id] = frozenset(tokens)
    return terms


def build_section_page_hints_from_outline(
    outline: DocumentOutline,
) -> tuple[tuple[str, int, int], ...]:
    """Section title phrases → 0-based page ranges from outline."""
    hints: list[tuple[str, int, int]] = []
    for unit in outline.units:
        for section in unit.sections:
            phrase = section.title.lower().strip()
            if len(phrase) >= _MIN_PHRASE_LEN:
                hints.append((phrase, section.page_start, section.page_end))
        unit_phrase = unit.title.lower().strip()
        if len(unit_phrase) >= _MIN_PHRASE_LEN:
            hints.append((unit_phrase, unit.page_start, unit.page_end))
    return tuple(hints)
