"""YAKE-style keyphrase extraction from exam question prompts (stdlib only)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_STOPWORDS = frozenset(
    """
    a an the and or but if then else when at by for with about against between into
    through during before after above below to from up down in out on off over under
    again further once here there all each few more most other some such no nor not
    only own same so than too very can will just don should now what which who whom
    this that these those am is are was were be been being have has had do does did
    doing would could ought i you he she it we they me him her us them my your his
    its our their of any five following each explain define describe compute state
    list give write name discuss differentiate between
    """.split()
)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")
_PAREN_ACRONYM_RE = re.compile(
    r"([A-Za-z][A-Za-z\s\-]{2,}?)\s*\(([A-Z]{2,})\)",
)


@dataclass(frozen=True, slots=True)
class ExtractedPhrase:
    text: str
    normalized: str
    score: float
    is_acronym: bool = False


def normalize_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    return cleaned


def extract_acronym_links(text: str) -> dict[str, str]:
    """Map normalized acronym -> normalized long form."""
    links: dict[str, str] = {}
    for match in _PAREN_ACRONYM_RE.finditer(text):
        long_form = normalize_phrase(match.group(1))
        acronym = normalize_phrase(match.group(2))
        if long_form and acronym:
            links[acronym] = long_form
    for token in _ACRONYM_RE.findall(text):
        acronym = normalize_phrase(token)
        if acronym and acronym not in links:
            links[acronym] = acronym
    return links


def _candidate_phrases(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(phrase: str) -> None:
        normalized = normalize_phrase(phrase)
        if len(normalized) < 3 or normalized in seen:
            return
        if normalized in _STOPWORDS:
            return
        seen.add(normalized)
        candidates.append(phrase.strip())

    for match in _PAREN_ACRONYM_RE.finditer(text):
        add(match.group(1))
        add(match.group(2))

    for token in _ACRONYM_RE.findall(text):
        add(token)

    tokens = [t for t in _TOKEN_RE.findall(text) if normalize_phrase(t) not in _STOPWORDS]
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i : i + n])
            add(gram)

    return candidates


def _yake_score(phrase: str, text: str, positions: list[int]) -> float:
    normalized = normalize_phrase(phrase)
    if not normalized:
        return 0.0
    tf = max(1, len(re.findall(re.escape(normalized), normalize_phrase(text), flags=re.I)))
    casing_bonus = 1.5 if phrase.isupper() or phrase[:1].isupper() else 1.0
    length_bonus = min(3.0, 1.0 + (len(normalized.split()) - 1) * 0.35)
    position_term = sum(1.0 / math.log2(pos + 2) for pos in positions) / len(positions)
    raw = (position_term / tf) * casing_bonus * length_bonus
    return min(1.0, raw / 2.5)


def extract_keyphrases(prompt_text: str, *, max_phrases: int = 8) -> list[ExtractedPhrase]:
    """Extract ranked keyphrases from one exam question prompt."""
    if not prompt_text or not prompt_text.strip():
        return []

    text = prompt_text.strip()
    acronym_links = extract_acronym_links(text)
    scored: dict[str, ExtractedPhrase] = {}

    for phrase in _candidate_phrases(text):
        normalized = normalize_phrase(phrase)
        positions = [m.start() for m in re.finditer(re.escape(normalized), normalize_phrase(text), flags=re.I)]
        if not positions:
            positions = [0]
        score = _yake_score(phrase, text, positions)
        is_acronym = normalized in acronym_links and normalized != acronym_links[normalized]
        display = phrase.strip()
        if normalized in acronym_links and acronym_links[normalized] != normalized:
            long_form = acronym_links[normalized]
            display = long_form
            normalized = long_form
            is_acronym = True
        existing = scored.get(normalized)
        if existing is None or score > existing.score:
            scored[normalized] = ExtractedPhrase(
                text=display,
                normalized=normalized,
                score=score,
                is_acronym=is_acronym,
            )

    ranked = sorted(scored.values(), key=lambda item: (-item.score, -len(item.normalized), item.normalized))
    return ranked[:max_phrases]
