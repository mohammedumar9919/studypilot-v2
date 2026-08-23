"""Greedy FastEmbed cosine merge for canonical exam concept labels."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from app.services.embedder import embed_texts
from app.services.exam.concept_extract import ExtractedPhrase, normalize_phrase

MERGE_COSINE_THRESHOLD = 0.82
MIN_QUESTIONS_FOR_CLUSTERING = 5
SYLLABUS_LABEL_THRESHOLD = 0.78
_NOISE_ONLY = re.compile(r"^(how|what|applications|explain|define|discuss|describe)\b", re.IGNORECASE)


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


def _is_noise_label(text: str) -> bool:
    normalized = normalize_phrase(text)
    tokens = normalized.split()
    if len(tokens) <= 1:
        return True
    if _NOISE_ONLY.match(normalized) and len(tokens) <= 3:
        return True
    return False


def _pick_cluster_label(
    terms: list[ExtractedPhrase],
    *,
    subtopic_titles: list[str] | None = None,
) -> str:
    candidates = sorted(terms, key=lambda item: (-item.score, -len(item.normalized), item.normalized))
    filtered = [item for item in candidates if not _is_noise_label(item.text)]
    pool = filtered or candidates

    if subtopic_titles:
        title_vectors = embed_texts(subtopic_titles)
        best_title: str | None = None
        best_sim = -1.0
        for phrase in pool[:5]:
            phrase_vector = embed_texts([phrase.text])[0]
            for title, title_vector in zip(subtopic_titles, title_vectors, strict=True):
                sim = _cosine_similarity(phrase_vector, title_vector)
                if sim > best_sim:
                    best_sim = sim
                    best_title = title
        if best_title and best_sim >= SYLLABUS_LABEL_THRESHOLD:
            return best_title

    return pool[0].text


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
        return [
            ConceptCluster(label=item.text, terms=(item.normalized,), confidence=item.score)
            for item in ordered
        ]

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
        terms = sorted(cluster["terms"], key=lambda item: (-item.score, -len(item.normalized), item.normalized))
        label = _pick_cluster_label(terms, subtopic_titles=subtopic_titles)
        normalized_terms = tuple(dict.fromkeys(normalize_phrase(item.normalized) for item in terms))
        confidence = sum(item.score for item in terms) / len(terms)
        result.append(
            ConceptCluster(
                label=label,
                terms=normalized_terms,
                confidence=confidence,
            )
        )
    return result
