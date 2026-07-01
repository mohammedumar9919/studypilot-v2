"""Greedy FastEmbed cosine merge for canonical exam concept labels."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.embedder import embed_texts
from app.services.exam.concept_extract import ExtractedPhrase, normalize_phrase

MERGE_COSINE_THRESHOLD = 0.82
MIN_QUESTIONS_FOR_CLUSTERING = 5


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


def canonicalize_phrases(
    phrases: list[ExtractedPhrase],
    *,
    question_count: int,
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
        label = terms[0].text
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
