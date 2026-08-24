"""No-LLM heuristic likely-topic / unit predictions from exam analytics rows."""

from __future__ import annotations

from typing import Any

FORMULA_VERSION = "v1"
DEFAULT_TOP_N = 10
DEFAULT_UNIT_TOP_N = 5
DEFAULT_TOPIC_TOP_N = 5

_W_WEIGHTAGE = 0.45
_W_RECURRENCE = 0.35
_W_TREND = 0.20

_HIGH_WEIGHTAGE_NORM = 0.6
_RECURS_THRESHOLD = 0.5

KIND_CONCEPT = "concept"
KIND_UNIT = "unit"
KIND_TOPIC = "topic"


def _norm_max(values: list[float]) -> list[float]:
    if not values:
        return []
    peak = max(values)
    if peak <= 0:
        return [0.0] * len(values)
    return [v / peak for v in values]


def _norm_trend(slopes: list[float | None]) -> list[float]:
    present = [s for s in slopes if s is not None]
    if not present:
        return [0.0] * len(slopes)
    lo = min(present)
    hi = max(present)
    if hi == lo:
        return [1.0 if s is not None else 0.0 for s in slopes]
    span = hi - lo
    return [((s - lo) / span) if s is not None else 0.0 for s in slopes]


def _reasons(
    *,
    norm_weightage: float,
    recurrence_rate: float,
    trend_slope: float | None,
) -> list[str]:
    reasons: list[str] = []
    if norm_weightage >= _HIGH_WEIGHTAGE_NORM:
        reasons.append("high_weightage")
    if recurrence_rate >= _RECURS_THRESHOLD:
        reasons.append("recurs_across_papers")
    if trend_slope is not None and trend_slope > 0:
        reasons.append("rising_trend")
    return reasons


def _linear_slope(year_counts: dict[str, float]) -> float | None:
    if len(year_counts) < 2:
        return None
    pairs = sorted((int(year), float(count)) for year, count in year_counts.items() if str(year).isdigit())
    if len(pairs) < 2:
        return None
    xs = [float(i) for i, _ in enumerate(pairs)]
    ys = [count for _, count in pairs]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom <= 0:
        return 0.0
    numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return round(numer / denom, 4)


def _score_rows(
    rows: list[dict[str, Any]],
    *,
    kind: str,
    top_n: int,
    id_key: str,
    label_key: str,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    weightages = [float(row.get("weightage_pct") or 0.0) for row in rows]
    recurrences = [float(row.get("recurrence_rate") or 0.0) for row in rows]
    slopes: list[float | None] = []
    for row in rows:
        raw = row.get("trend_slope")
        slopes.append(float(raw) if raw is not None else None)

    norm_w = _norm_max(weightages)
    norm_t = _norm_trend(slopes)

    scored: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        nw = norm_w[idx]
        rr = recurrences[idx]
        nt = norm_t[idx]
        slope = slopes[idx]
        score = round(_W_WEIGHTAGE * nw + _W_RECURRENCE * rr + _W_TREND * nt, 4)
        item: dict[str, Any] = {
            "kind": kind,
            "label": str(row.get(label_key) or ""),
            "score": score,
            "reasons": _reasons(
                norm_weightage=nw,
                recurrence_rate=rr,
                trend_slope=slope,
            ),
        }
        row_id = row.get(id_key)
        if row_id is not None and str(row_id):
            item[id_key] = str(row_id)
        # Backward-compatible concept fields on concept items.
        if kind == KIND_CONCEPT:
            item["concept_id"] = str(row.get("concept_id") or "")
        concept_id = row.get("concept_id")
        if concept_id is not None and str(concept_id) and kind != KIND_CONCEPT:
            item["concept_id"] = str(concept_id)
        unit_id = row.get("unit_id")
        if unit_id is not None and str(unit_id):
            item["unit_id"] = str(unit_id)
        scored.append(item)

    scored.sort(key=lambda item: (-item["score"], item["label"].lower()))
    items = scored[: max(1, top_n)]
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank
    return items


def build_predictions(
    concept_rows: list[dict[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
    unit_rows: list[dict[str, Any]] | None = None,
    topic_rows: list[dict[str, Any]] | None = None,
    unit_top_n: int = DEFAULT_UNIT_TOP_N,
    topic_top_n: int = DEFAULT_TOPIC_TOP_N,
) -> dict[str, Any]:
    """Rank concept / unit / topic analytics rows into a predictions block (pure, no I/O)."""
    top_n = max(1, top_n)
    items = _score_rows(
        concept_rows,
        kind=KIND_CONCEPT,
        top_n=top_n,
        id_key="concept_id",
        label_key="label",
    )
    units = _score_rows(
        unit_rows or [],
        kind=KIND_UNIT,
        top_n=unit_top_n,
        id_key="unit_id",
        label_key="label",
    )
    topics = _score_rows(
        topic_rows or [],
        kind=KIND_TOPIC,
        top_n=topic_top_n,
        id_key="topic_id",
        label_key="label",
    )
    return {
        "items": items,
        "units": units,
        "topics": topics,
        "formula_version": FORMULA_VERSION,
        "top_n": top_n,
    }


def empty_predictions(*, top_n: int = DEFAULT_TOP_N) -> dict[str, Any]:
    return {
        "items": [],
        "units": [],
        "topics": [],
        "formula_version": FORMULA_VERSION,
        "top_n": max(1, top_n),
    }


def unit_rows_from_syllabus_primary(syllabus_block: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convert syllabus_primary.units + year_unit_matrix into scorable unit rows."""
    if not syllabus_block:
        return []
    units = list(syllabus_block.get("units") or [])
    matrix = syllabus_block.get("year_unit_matrix") or {}
    years = sorted(str(year) for year in matrix.keys())
    paper_count = int((syllabus_block.get("summary") or {}).get("paper_count") or 0)
    year_count = max(len(years), 1)

    rows: list[dict[str, Any]] = []
    for unit in units:
        label = str(unit.get("unit") or "").strip()
        if not label or label.lower() in {"unmapped", "unclassified"}:
            continue
        year_counts: dict[str, float] = {}
        years_present = 0
        for year in years:
            count = float((matrix.get(year) or {}).get(label) or 0)
            if count > 0:
                years_present += 1
                year_counts[year] = count
        # Recurrence proxy: share of years (or papers) where the unit appears.
        recurrence = years_present / year_count if years else (1.0 if paper_count else 0.0)
        rows.append(
            {
                "unit_id": label,
                "label": label,
                "weightage_pct": float(unit.get("subpart_pct") or 0.0),
                "recurrence_rate": round(recurrence, 4),
                "trend_slope": _linear_slope(year_counts),
            }
        )
    return rows


def unit_rows_from_structure(structure: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convert tier-3 structure.units into scorable unit rows (prefer mapped concept for tap)."""
    if not structure:
        return []
    rows: list[dict[str, Any]] = []
    for unit in structure.get("units") or []:
        label = str(unit.get("title") or "").strip()
        if not label:
            continue
        mapped = list(unit.get("mapped_concept_ids") or [])
        rows.append(
            {
                "unit_id": str(unit.get("unit_id") or label),
                "label": label,
                "weightage_pct": float(unit.get("weightage_pct") or 0.0),
                "recurrence_rate": float(unit.get("recurrence_rate") or 0.0),
                "trend_slope": None,
                "concept_id": mapped[0] if mapped else None,
            }
        )
    return rows


def topic_rows_from_syllabus_primary(syllabus_block: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Cheap topic predictions from syllabus_primary.top_topics (count as weightage proxy)."""
    if not syllabus_block:
        return []
    topics = list(syllabus_block.get("top_topics") or [])
    if not topics:
        return []
    peak = max(float(row.get("count") or 0.0) for row in topics) or 1.0
    rows: list[dict[str, Any]] = []
    for topic in topics:
        label = str(topic.get("name") or "").strip()
        if not label:
            continue
        count = float(topic.get("count") or 0.0)
        rows.append(
            {
                "topic_id": label,
                "label": label,
                "weightage_pct": float(topic.get("pct") or (count / peak * 100.0)),
                "recurrence_rate": min(1.0, count / peak) if peak else 0.0,
                "trend_slope": None,
            }
        )
    return rows


def attach_unit_predictions(
    predictions: dict[str, Any],
    *,
    syllabus_block: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enrich a predictions block with units/topics from syllabus or structure (pure)."""
    result = dict(predictions)
    result.setdefault("items", [])
    result.setdefault("units", [])
    result.setdefault("topics", [])

    structure_units = unit_rows_from_structure(structure)
    syllabus_units = unit_rows_from_syllabus_primary(syllabus_block)
    # Prefer structure (mapped + concept_id for answer-on-tap) when present.
    unit_source = structure_units if structure_units else syllabus_units
    if unit_source and not result.get("units"):
        result["units"] = _score_rows(
            unit_source,
            kind=KIND_UNIT,
            top_n=DEFAULT_UNIT_TOP_N,
            id_key="unit_id",
            label_key="label",
        )

    topic_source = topic_rows_from_syllabus_primary(syllabus_block)
    if topic_source and not result.get("topics"):
        result["topics"] = _score_rows(
            topic_source,
            kind=KIND_TOPIC,
            top_n=DEFAULT_TOPIC_TOP_N,
            id_key="topic_id",
            label_key="label",
        )
    return result
