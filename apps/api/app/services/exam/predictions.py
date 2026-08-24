"""No-LLM heuristic likely-topic predictions from exam concept analytics rows."""

from __future__ import annotations

from typing import Any

FORMULA_VERSION = "v1"
DEFAULT_TOP_N = 10

_W_WEIGHTAGE = 0.45
_W_RECURRENCE = 0.35
_W_TREND = 0.20

_HIGH_WEIGHTAGE_NORM = 0.6
_RECURS_THRESHOLD = 0.5


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


def build_predictions(
    concept_rows: list[dict[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """Rank concept analytics rows into a predictions block (pure, no I/O)."""
    top_n = max(1, top_n)
    if not concept_rows:
        return {
            "items": [],
            "formula_version": FORMULA_VERSION,
            "top_n": top_n,
        }

    weightages = [float(row.get("weightage_pct") or 0.0) for row in concept_rows]
    recurrences = [float(row.get("recurrence_rate") or 0.0) for row in concept_rows]
    slopes: list[float | None] = []
    for row in concept_rows:
        raw = row.get("trend_slope")
        slopes.append(float(raw) if raw is not None else None)

    norm_w = _norm_max(weightages)
    norm_t = _norm_trend(slopes)

    scored: list[dict[str, Any]] = []
    for idx, row in enumerate(concept_rows):
        nw = norm_w[idx]
        rr = recurrences[idx]
        nt = norm_t[idx]
        slope = slopes[idx]
        score = round(_W_WEIGHTAGE * nw + _W_RECURRENCE * rr + _W_TREND * nt, 4)
        scored.append(
            {
                "concept_id": str(row.get("concept_id") or ""),
                "label": str(row.get("label") or ""),
                "score": score,
                "reasons": _reasons(
                    norm_weightage=nw,
                    recurrence_rate=rr,
                    trend_slope=slope,
                ),
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["label"].lower()))
    items = scored[:top_n]
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank

    return {
        "items": items,
        "formula_version": FORMULA_VERSION,
        "top_n": top_n,
    }


def empty_predictions(*, top_n: int = DEFAULT_TOP_N) -> dict[str, Any]:
    return {
        "items": [],
        "formula_version": FORMULA_VERSION,
        "top_n": max(1, top_n),
    }
