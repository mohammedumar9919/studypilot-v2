"""Tier 3 exam analytics — map concepts onto course structure tree (SP-060c)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from sqlalchemy.orm import Session

from app.models import Course, ExamConcept, ExamQuestion, ExamQuestionConcept
from app.services.course_structure import get_course_structure
from app.services.embedder import embed_texts
from app.services.exam.analytics import (
    LONG_QUESTION_THRESHOLD_MARKS,
    _question_marks,
)
from app.services.study_layout import resolve_structure_mode

EMBED_MATCH_THRESHOLD = 0.75
TIE_BREAK_EPSILON = 0.02
_NODE_TYPE_RANK = {"subtopic": 3, "part": 2, "unit": 1}

IncludeStructureMode = Literal["auto", "true", "false"]
_VALID_INCLUDE_STRUCTURE = frozenset({"auto", "true", "false"})


@dataclass
class StructureNode:
    node_id: str
    title: str
    node_type: str
    unit_id: str
    part_id: str | None = None
    children: list[StructureNode] = field(default_factory=list)
    parent_id: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _concept_terms(concept: ExamConcept) -> list[str]:
    terms = [concept.label, *(concept.canonical_terms or [])]
    terms.extend(alias.alias for alias in concept.aliases)
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        normalized = _normalize(term)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def is_tier3_eligible(session: Session, course_id: str) -> bool:
    course = session.get(Course, course_id)
    if course is None:
        return False
    if resolve_structure_mode(course_id, course=course) != "mapped":
        return False
    structure = get_course_structure(session, course_id)
    return bool(structure and structure.get("units"))


def _build_structure_nodes(structure: dict[str, Any]) -> tuple[list[StructureNode], dict[str, StructureNode]]:
    nodes: list[StructureNode] = []
    by_id: dict[str, StructureNode] = {}

    for unit in structure.get("units", []):
        unit_node = StructureNode(
            node_id=str(unit["id"]),
            title=str(unit["title"]),
            node_type="unit",
            unit_id=str(unit["id"]),
        )
        nodes.append(unit_node)
        by_id[unit_node.node_id] = unit_node

        if unit.get("parts"):
            for part in unit["parts"]:
                part_node = StructureNode(
                    node_id=str(part["id"]),
                    title=str(part["title"]),
                    node_type="part",
                    unit_id=unit_node.node_id,
                    part_id=str(part["id"]),
                    parent_id=unit_node.node_id,
                )
                unit_node.children.append(part_node)
                nodes.append(part_node)
                by_id[part_node.node_id] = part_node

                for subtopic in part.get("subtopics") or []:
                    subtopic_node = StructureNode(
                        node_id=str(subtopic["id"]),
                        title=str(subtopic["title"]),
                        node_type="subtopic",
                        unit_id=unit_node.node_id,
                        part_id=part_node.node_id,
                        parent_id=part_node.node_id,
                    )
                    part_node.children.append(subtopic_node)
                    nodes.append(subtopic_node)
                    by_id[subtopic_node.node_id] = subtopic_node
        else:
            for subtopic in unit.get("subtopics") or []:
                subtopic_node = StructureNode(
                    node_id=str(subtopic["id"]),
                    title=str(subtopic["title"]),
                    node_type="subtopic",
                    unit_id=unit_node.node_id,
                    parent_id=unit_node.node_id,
                )
                unit_node.children.append(subtopic_node)
                nodes.append(subtopic_node)
                by_id[subtopic_node.node_id] = subtopic_node

    return nodes, by_id


def _substring_score(concept_terms: list[str], node_title: str) -> float:
    normalized_title = _normalize(node_title)
    for term in concept_terms:
        if len(term) < 3:
            continue
        if term in normalized_title or normalized_title in term:
            return 1.0
    return 0.0


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _labels_for_matched_node(
    node: StructureNode,
    by_id: dict[str, StructureNode],
) -> tuple[str, str, str]:
    if node.node_type == "unit":
        return node.title, node.title, node.title

    if node.node_type == "part":
        unit_node = by_id.get(node.parent_id or "")
        unit_title = unit_node.title if unit_node else node.title
        return unit_title, node.title, node.title

    subtopic_title = node.title
    parent = by_id.get(node.parent_id or "") if node.parent_id else None
    if parent and parent.node_type == "part":
        unit_node = by_id.get(parent.parent_id or "")
        unit_title = unit_node.title if unit_node else parent.title
        return unit_title, parent.title, subtopic_title

    unit_title = parent.title if parent else subtopic_title
    return unit_title, subtopic_title, subtopic_title


def _prompt_terms(prompt: str, *, extra_terms: list[str] | None = None) -> list[str]:
    terms = [_normalize(prompt)]
    for term in extra_terms or []:
        normalized = _normalize(term)
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms


def match_prompt_to_structure(
    prompt: str,
    structure: dict[str, Any],
    *,
    extra_terms: list[str] | None = None,
) -> tuple[str, str, str] | None:
    """Map an exam prompt onto mapped syllabus node titles (unit, topic, subtopic)."""
    if not prompt.strip() or not structure.get("units"):
        return None

    nodes, by_id = _build_structure_nodes(structure)
    if not nodes:
        return None

    terms = _prompt_terms(prompt, extra_terms=extra_terms)
    prompt_vector = embed_texts([prompt.strip()])[0]
    node_vectors = embed_texts([node.title for node in nodes])

    best_node: StructureNode | None = None
    best_score = -1.0
    best_rank = -1

    for node, node_vector in zip(nodes, node_vectors, strict=True):
        score = max(_substring_score(terms, node.title), _cosine_similarity(prompt_vector, node_vector))
        rank = _NODE_TYPE_RANK[node.node_type]
        if score > best_score + TIE_BREAK_EPSILON or (
            abs(score - best_score) <= TIE_BREAK_EPSILON and rank > best_rank
        ):
            best_score = score
            best_rank = rank
            best_node = node

    if best_node is None or best_score < EMBED_MATCH_THRESHOLD:
        return None

    return _labels_for_matched_node(best_node, by_id)


def auto_map_concepts_to_nodes(
    concepts: list[ExamConcept],
    nodes: list[StructureNode],
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Return node_id -> concept_ids and unmapped concept summaries."""
    classified = [concept for concept in concepts if not concept.is_unclassified]
    if not classified or not nodes:
        unmapped = [
            {"concept_id": str(concept.id), "label": concept.label}
            for concept in classified
        ]
        return {}, unmapped

    node_titles = [node.title for node in nodes]
    concept_labels = [concept.label for concept in classified]
    node_vectors = embed_texts(node_titles)
    concept_vectors = embed_texts(concept_labels)

    node_assignments: dict[str, list[str]] = defaultdict(list)
    unmapped: list[dict[str, Any]] = []

    for concept, concept_vector in zip(classified, concept_vectors, strict=True):
        terms = _concept_terms(concept)
        best_node: StructureNode | None = None
        best_score = -1.0
        best_rank = -1

        for node, node_vector in zip(nodes, node_vectors, strict=True):
            score = max(_substring_score(terms, node.title), _cosine_similarity(concept_vector, node_vector))
            rank = _NODE_TYPE_RANK[node.node_type]
            if score > best_score + TIE_BREAK_EPSILON or (
                abs(score - best_score) <= TIE_BREAK_EPSILON and rank > best_rank
            ):
                best_score = score
                best_rank = rank
                best_node = node

        if best_node is None or best_score < EMBED_MATCH_THRESHOLD:
            unmapped.append({"concept_id": str(concept.id), "label": concept.label})
            continue

        node_assignments[best_node.node_id].append(str(concept.id))

    return dict(node_assignments), unmapped


def _empty_metrics() -> dict[str, Any]:
    return {
        "question_count": 0.0,
        "unique_question_count": 0,
        "marks_total": 0.0,
        "weightage_pct": 0.0,
        "count_pct": 0.0,
        "long_count": 0,
        "short_count": 0,
        "paper_reach": 0,
        "recurrence_rate": 0.0,
        "concept_count": 0,
        "mapped_concept_ids": [],
    }


def _aggregate_node_metrics(
    concept_ids: list[str],
    *,
    concept_uuid_by_str: dict[str, Any],
    per_concept_links: dict[Any, list[ExamQuestionConcept]],
    question_by_id: dict[Any, ExamQuestion],
    parsed_questions: int,
    total_marks: int,
    distinct_paper_count: int,
) -> dict[str, Any]:
    if not concept_ids:
        return _empty_metrics()

    question_weights: dict[Any, float] = {}
    papers: set[str] = set()
    long_count = 0
    short_count = 0

    for concept_id in concept_ids:
        concept_uuid = concept_uuid_by_str.get(concept_id)
        if concept_uuid is None:
            continue
        for link in per_concept_links.get(concept_uuid, []):
            question = link.question or question_by_id.get(link.question_id)
            if question is None:
                continue
            question_weights[question.id] = max(question_weights.get(question.id, 0.0), link.weight)
            q_marks = _question_marks(question)
            if q_marks >= LONG_QUESTION_THRESHOLD_MARKS:
                long_count += 1
            else:
                short_count += 1
            if question.paper_label:
                papers.add(question.paper_label)

    marks_total = 0.0
    weighted_question_count = 0.0
    for question_id, weight in question_weights.items():
        question = question_by_id[question_id]
        q_marks = _question_marks(question)
        marks_total += q_marks * weight
        weighted_question_count += weight

    unique_question_count = len(question_weights)
    weightage_pct = round((marks_total / total_marks * 100.0) if total_marks else 0.0, 2)
    count_pct = round(
        (unique_question_count / parsed_questions * 100.0) if parsed_questions else 0.0,
        2,
    )
    paper_reach = len(papers)
    recurrence_rate = round(paper_reach / distinct_paper_count, 4) if distinct_paper_count else 0.0

    return {
        "question_count": round(weighted_question_count, 4),
        "unique_question_count": unique_question_count,
        "marks_total": round(marks_total, 2),
        "weightage_pct": weightage_pct,
        "count_pct": count_pct,
        "long_count": long_count,
        "short_count": short_count,
        "paper_reach": paper_reach,
        "recurrence_rate": recurrence_rate,
        "concept_count": len(concept_ids),
        "mapped_concept_ids": concept_ids,
    }


def _collect_subtree_concept_ids(
    node: StructureNode,
    node_assignments: dict[str, list[str]],
) -> list[str]:
    concept_ids = list(node_assignments.get(node.node_id, []))
    for child in node.children:
        concept_ids.extend(_collect_subtree_concept_ids(child, node_assignments))
    return list(dict.fromkeys(concept_ids))


def _rollup_node_metrics(
    node: StructureNode,
    node_assignments: dict[str, list[str]],
    *,
    concept_uuid_by_str: dict[str, Any],
    per_concept_links: dict[Any, list[ExamQuestionConcept]],
    question_by_id: dict[Any, ExamQuestion],
    parsed_questions: int,
    total_marks: int,
    distinct_paper_count: int,
    metrics_by_node: dict[str, dict[str, Any]],
) -> None:
    for child in node.children:
        _rollup_node_metrics(
            child,
            node_assignments,
            concept_uuid_by_str=concept_uuid_by_str,
            per_concept_links=per_concept_links,
            question_by_id=question_by_id,
            parsed_questions=parsed_questions,
            total_marks=total_marks,
            distinct_paper_count=distinct_paper_count,
            metrics_by_node=metrics_by_node,
        )

    concept_ids = _collect_subtree_concept_ids(node, node_assignments)
    metrics_by_node[node.node_id] = _aggregate_node_metrics(
        concept_ids,
        concept_uuid_by_str=concept_uuid_by_str,
        per_concept_links=per_concept_links,
        question_by_id=question_by_id,
        parsed_questions=parsed_questions,
        total_marks=total_marks,
        distinct_paper_count=distinct_paper_count,
    )


def _serialize_subtopic(
    subtopic: dict[str, Any],
    metrics_by_node: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metrics = metrics_by_node.get(str(subtopic["id"]), _empty_metrics())
    return {
        "subtopic_id": str(subtopic["id"]),
        "title": subtopic["title"],
        **metrics,
    }


def _serialize_part(
    part: dict[str, Any],
    metrics_by_node: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    subtopics = [_serialize_subtopic(item, metrics_by_node) for item in part.get("subtopics") or []]
    metrics = metrics_by_node.get(str(part["id"]), _empty_metrics())
    return {
        "part_id": str(part["id"]),
        "title": part["title"],
        **metrics,
        "subtopics": subtopics,
    }


def _serialize_unit(
    unit: dict[str, Any],
    metrics_by_node: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "unit_id": str(unit["id"]),
        "title": unit["title"],
        **metrics_by_node.get(str(unit["id"]), _empty_metrics()),
    }
    if unit.get("parts"):
        payload["parts"] = [_serialize_part(part, metrics_by_node) for part in unit["parts"]]
    else:
        payload["subtopics"] = [
            _serialize_subtopic(subtopic, metrics_by_node) for subtopic in unit.get("subtopics") or []
        ]
    return payload


def build_structure_analytics(
    session: Session,
    course_id: str,
    *,
    concepts: list[ExamConcept],
    links: list[ExamQuestionConcept],
    questions: list[ExamQuestion],
    parsed_questions: int,
    total_marks: int,
    distinct_paper_count: int,
) -> dict[str, Any]:
    structure = get_course_structure(session, course_id)
    if not structure:
        return {"structure_mode": "mapped", "units": [], "unmapped_concepts": []}

    nodes, _ = _build_structure_nodes(structure)
    top_level = [node for node in nodes if node.node_type == "unit"]
    node_assignments, unmapped_concepts = auto_map_concepts_to_nodes(concepts, nodes)

    question_by_id = {question.id: question for question in questions}
    per_concept_links: dict[Any, list[ExamQuestionConcept]] = defaultdict(list)
    for link in links:
        per_concept_links[link.concept_id].append(link)
    concept_uuid_by_str = {str(concept.id): concept.id for concept in concepts}

    metrics_by_node: dict[str, dict[str, Any]] = {}
    for unit_node in top_level:
        _rollup_node_metrics(
            unit_node,
            node_assignments,
            concept_uuid_by_str=concept_uuid_by_str,
            per_concept_links=per_concept_links,
            question_by_id=question_by_id,
            parsed_questions=parsed_questions,
            total_marks=total_marks,
            distinct_paper_count=distinct_paper_count,
            metrics_by_node=metrics_by_node,
        )

    return {
        "structure_mode": "mapped",
        "units": [_serialize_unit(unit, metrics_by_node) for unit in structure["units"]],
        "unmapped_concepts": unmapped_concepts,
    }


def maybe_attach_structure(
    session: Session,
    course_id: str,
    payload: dict[str, Any],
    *,
    include_structure: str,
    concepts: list[ExamConcept],
    links: list[ExamQuestionConcept],
    questions: list[ExamQuestion],
    parsed_questions: int,
    total_marks: int,
    distinct_paper_count: int,
) -> dict[str, Any]:
    if include_structure not in _VALID_INCLUDE_STRUCTURE:
        raise ValueError(f"Unsupported include_structure: {include_structure}")

    if not payload.get("analytics_ready"):
        return payload

    if include_structure == "false":
        return payload

    if include_structure == "auto" and not is_tier3_eligible(session, course_id):
        return payload

    if include_structure == "true" and not is_tier3_eligible(session, course_id):
        return payload

    structure_block = build_structure_analytics(
        session,
        course_id,
        concepts=concepts,
        links=links,
        questions=questions,
        parsed_questions=parsed_questions,
        total_marks=total_marks,
        distinct_paper_count=distinct_paper_count,
    )
    payload = dict(payload)
    payload["tier"] = 3
    payload["structure"] = {
        "structure_mode": structure_block["structure_mode"],
        "units": structure_block["units"],
    }
    payload["unmapped_concepts"] = structure_block["unmapped_concepts"]
    return payload
