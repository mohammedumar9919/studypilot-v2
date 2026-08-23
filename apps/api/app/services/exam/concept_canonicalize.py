"""Greedy FastEmbed cosine merge for canonical exam concept labels."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from app.services.embedder import embed_texts
from app.services.exam.concept_extract import ExtractedPhrase, normalize_phrase

MERGE_COSINE_THRESHOLD = 0.82
MIN_QUESTIONS_FOR_CLUSTERING = 5
SYLLABUS_LABEL_THRESHOLD = 0.72

_ACRONYM_WHITELIST = frozenset(
    """
    edta ro cng lpg pvc pla hcv lcv ph emf adt ou zn pb li ion co2 h2 o2 oop adt
    """.split()
)

_GENERIC_LABEL_TOKENS = frozenset(
    """
    applications application properties property preparation mechanism construction
    working brief note explain define discuss describe compute state list give write
    name differentiate between mustrate demonstrate derive draw sketch what how why
    when where important general various following any five available carry calculate
    degree impact structure classification classify types type method methods principle
    principles introduction overview features advantages disadvantages uses use role
    function functions process processes reaction reactions equation equations diagram
    neat detail examples example significance importance effect effects factors factor
    comparison compare difference differences classify applications classification
    constituents constituent composition characteristic characteristics relevant concept
    concepts trans exchange method sources source influencing rate addition illustrate
    cracking significance determined estimation evolution conduction using cell cells
    """.split()
)

_NOISE_ONLY = re.compile(
    r"^(how|what|applications?|explain|define|discuss|describe|brief|note|give|list|write|state|compute|derive|draw|sketch|demonstrate|mustrate|and|or|the)\b",
    re.IGNORECASE,
)
_INCOMPLETE_SUFFIX = re.compile(
    r"\b(of|and|or|the|a|an|in|on|for|with|to|from|by|at|is|are|was|were)\s*$",
    re.IGNORECASE,
)
_LEADING_FILLER = re.compile(
    r"^(and|or|the|a|an|of|in|on|for|with|to|from|by|at)\s+",
    re.IGNORECASE,
)
_OCR_JUNK = re.compile(
    r"\b(datemnine|hewardness|diselss|janent|bed-worth|mustrate|diselss th)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ConceptCluster:
    label: str
    terms: tuple[str, ...]
    confidence: float


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _content_tokens(normalized: str) -> list[str]:
    return [token for token in normalized.split() if token not in _GENERIC_LABEL_TOKENS]


def _is_garbage_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in _ACRONYM_WHITELIST:
        return False
    if len(token) <= 2:
        return True
    if len(token) <= 3 and token.isupper():
        return True
    if _OCR_JUNK.search(token):
        return True
    return False


def _phrase_specificity(item: ExtractedPhrase) -> tuple[int, int, int, float, str]:
    content = _content_tokens(item.normalized)
    tokens = item.normalized.split()
    return (len(content), len(tokens), len(item.normalized), item.score, item.normalized)


def _polish_label(text: str) -> str:
    polished = normalize_phrase(text)
    while _LEADING_FILLER.match(polished):
        polished = _LEADING_FILLER.sub("", polished, count=1)
    return _titleize_phrase(polished)


def _is_noise_label(text: str) -> bool:
    normalized = normalize_phrase(text)
    if _OCR_JUNK.search(normalized):
        return True
    tokens = normalized.split()
    if not tokens:
        return True
    if len(tokens) <= 1:
        return True
    if _INCOMPLETE_SUFFIX.search(normalized):
        return True
    if _NOISE_ONLY.match(normalized) and len(tokens) <= 4:
        return True
    if any(_is_garbage_token(token) for token in tokens):
        return True
    if len(tokens) >= 2 and len(set(tokens)) < len(tokens) and all(len(token) <= 4 for token in tokens):
        return True
    content = _content_tokens(normalized)
    if not content:
        return True
    if len(tokens) > len(content):
        # e.g. "constituents composites" — generic frame + one topic word
        return len(content) < 2
    if len(content) == 1:
        return len(content[0]) < 6
    if len(content) == 2 and all(len(token) < 5 for token in content):
        return True
    return False


def _rank_label_candidates(candidates: list[ExtractedPhrase]) -> list[ExtractedPhrase]:
    return sorted(
        candidates,
        key=lambda item: (
            -_phrase_specificity(item)[0],
            -_phrase_specificity(item)[1],
            -_phrase_specificity(item)[2],
            -item.score,
            item.normalized,
        ),
    )


def _titleize_phrase(text: str) -> str:
    words = text.split()
    if not words:
        return text
    return " ".join(word[:1].upper() + word[1:] if word else word for word in words)


def _label_from_normalized_term(term: str) -> str | None:
    tokens = term.split()
    content = _content_tokens(term)
    if len(content) >= 2:
        return _titleize_phrase(" ".join(content))
    if len(content) == 1 and len(content[0]) >= 6:
        return _titleize_phrase(content[0])
    return None


def _substantive_fallback(candidates: list[ExtractedPhrase]) -> str | None:
    for item in _rank_label_candidates(candidates):
        rebuilt = _label_from_normalized_term(item.normalized)
        if rebuilt and not _is_noise_label(rebuilt):
            return rebuilt
    for item in _rank_label_candidates(candidates):
        polished = _polish_label(item.text)
        if not _is_noise_label(polished):
            return polished
    return None


def _pick_cluster_label(
    terms: list[ExtractedPhrase],
    *,
    subtopic_titles: list[str] | None = None,
) -> str | None:
    candidates = _rank_label_candidates(terms)
    filtered = [item for item in candidates if not _is_noise_label(item.text)]

    if subtopic_titles:
        title_vectors = embed_texts(subtopic_titles)
        best_title: str | None = None
        best_sim = -1.0
        for phrase in (filtered or candidates)[:10]:
            phrase_vector = embed_texts([phrase.text])[0]
            for title, title_vector in zip(subtopic_titles, title_vectors, strict=True):
                sim = _cosine_similarity(phrase_vector, title_vector)
                if sim > best_sim:
                    best_sim = sim
                    best_title = title
        if best_title and best_sim >= SYLLABUS_LABEL_THRESHOLD and not _is_noise_label(best_title):
            return best_title

    if filtered:
        label = _polish_label(filtered[0].text)
        return label if not _is_noise_label(label) else None

    fallback = _substantive_fallback(candidates)
    return _polish_label(fallback) if fallback else None


def _merge_clusters_by_label(clusters: list[ConceptCluster]) -> list[ConceptCluster]:
    merged: dict[str, ConceptCluster] = {}
    for cluster in clusters:
        key = normalize_phrase(cluster.label)
        existing = merged.get(key)
        if existing is None:
            merged[key] = cluster
            continue
        terms = tuple(dict.fromkeys(existing.terms + cluster.terms))
        confidence = (existing.confidence + cluster.confidence) / 2
        merged[key] = ConceptCluster(label=existing.label, terms=terms, confidence=confidence)
    return list(merged.values())


def canonicalize_phrases(
    phrases: list[ExtractedPhrase],
    *,
    question_count: int,
    subtopic_titles: list[str] | None = None,
) -> list[ConceptCluster]:
    """Merge near-duplicate phrases into canonical concept clusters."""
    if not phrases:
        return []

    unique: dict[str, ExtractedPhrase] = {}
    for phrase in phrases:
        current = unique.get(phrase.normalized)
        if current is None or phrase.score > current.score:
            unique[phrase.normalized] = phrase

    ordered = sorted(unique.values(), key=lambda item: (-item.score, -len(item.normalized), item.normalized))
    if question_count < MIN_QUESTIONS_FOR_CLUSTERING:
        result: list[ConceptCluster] = []
        for item in ordered:
            label = _pick_cluster_label([item], subtopic_titles=subtopic_titles)
            if not label or _is_noise_label(label):
                continue
            result.append(
                ConceptCluster(label=label, terms=(item.normalized,), confidence=item.score)
            )
        return _merge_clusters_by_label(result)

    embeddings = embed_texts([item.text for item in ordered])
    clusters: list[dict] = []

    for phrase, vector in zip(ordered, embeddings, strict=True):
        best_idx: int | None = None
        best_sim = -1.0
        for idx, cluster in enumerate(clusters):
            sim = _cosine_similarity(vector, cluster["vector"])
            if sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_idx is not None and best_sim >= MERGE_COSINE_THRESHOLD:
            cluster = clusters[best_idx]
            cluster["terms"].append(phrase)
            cluster["vector"] = np.mean([cluster["vector"], np.asarray(vector)], axis=0).tolist()
        else:
            clusters.append({"terms": [phrase], "vector": vector})

    result: list[ConceptCluster] = []
    for cluster in clusters:
        terms = list(cluster["terms"])
        label = _pick_cluster_label(terms, subtopic_titles=subtopic_titles)
        if not label or _is_noise_label(label):
            continue
        normalized_terms = tuple(dict.fromkeys(normalize_phrase(item.normalized) for item in terms))
        confidence = sum(item.score for item in terms) / len(terms)
        result.append(
            ConceptCluster(
                label=label,
                terms=normalized_terms,
                confidence=confidence,
            )
        )
    return _merge_clusters_by_label(result)
