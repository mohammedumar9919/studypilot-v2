"""Deterministic tests for SP-060f / SP-064f exam predictions heuristic."""

from __future__ import annotations

from app.services.exam.predictions import (
    FORMULA_VERSION,
    KIND_CONCEPT,
    KIND_TOPIC,
    KIND_UNIT,
    attach_unit_predictions,
    build_predictions,
    empty_predictions,
    unit_rows_from_structure,
    unit_rows_from_syllabus_primary,
)


def _row(
    *,
    concept_id: str,
    label: str,
    weightage_pct: float,
    recurrence_rate: float,
    trend_slope: float | None,
) -> dict:
    return {
        "concept_id": concept_id,
        "label": label,
        "weightage_pct": weightage_pct,
        "recurrence_rate": recurrence_rate,
        "trend_slope": trend_slope,
    }


def test_empty_concepts_yield_empty_items() -> None:
    result = build_predictions([])
    assert result["items"] == []
    assert result["units"] == []
    assert result["topics"] == []
    assert result["formula_version"] == FORMULA_VERSION
    assert result["top_n"] == 10
    assert empty_predictions()["items"] == []
    assert empty_predictions()["units"] == []


def test_score_order_weightage_recurrence_trend() -> None:
    """
    Fixture designed so ranking is deterministic under v1 weights:
      score = 0.45 * norm(w) + 0.35 * recurrence + 0.20 * norm_trend(slope)

    A: high weightage + high recurrence + rising → top
    B: mid weightage + high recurrence + flat
    C: low weightage + low recurrence + falling → bottom
    """
    rows = [
        _row(
            concept_id="c",
            label="Catalysts",
            weightage_pct=10.0,
            recurrence_rate=0.25,
            trend_slope=-1.0,
        ),
        _row(
            concept_id="a",
            label="Acids",
            weightage_pct=50.0,
            recurrence_rate=1.0,
            trend_slope=2.0,
        ),
        _row(
            concept_id="b",
            label="Bases",
            weightage_pct=30.0,
            recurrence_rate=0.75,
            trend_slope=0.0,
        ),
    ]

    result = build_predictions(rows, top_n=10)
    labels = [item["label"] for item in result["items"]]
    assert labels == ["Acids", "Bases", "Catalysts"]
    assert all(item["kind"] == KIND_CONCEPT for item in result["items"])

    acids, bases, catalysts = result["items"]
    # norm(w): 50/50=1, 30/50=0.6, 10/50=0.2
    # norm_trend slopes [-1,2,0]: lo=-1 hi=2 → Acids (2→1), Bases (0→1/3), Catalysts (-1→0)
    # Acids: 0.45*1 + 0.35*1 + 0.20*1 = 1.0
    assert acids["score"] == 1.0
    assert acids["rank"] == 1
    assert "high_weightage" in acids["reasons"]
    assert "recurs_across_papers" in acids["reasons"]
    assert "rising_trend" in acids["reasons"]

    # Bases: 0.45*0.6 + 0.35*0.75 + 0.20*(1/3) = 0.27 + 0.2625 + 0.066666... = 0.5992
    assert bases["score"] == 0.5992
    assert bases["rank"] == 2
    assert "high_weightage" in bases["reasons"]  # norm 0.6 >= 0.6
    assert "recurs_across_papers" in bases["reasons"]
    assert "rising_trend" not in bases["reasons"]

    # Catalysts: 0.45*0.2 + 0.35*0.25 + 0.20*0 = 0.09 + 0.0875 = 0.1775
    assert catalysts["score"] == 0.1775
    assert catalysts["rank"] == 3
    assert catalysts["reasons"] == []


def test_top_n_truncates_and_tie_break_by_label() -> None:
    rows = [
        _row(
            concept_id="2",
            label="Zebra",
            weightage_pct=20.0,
            recurrence_rate=0.5,
            trend_slope=None,
        ),
        _row(
            concept_id="1",
            label="Alpha",
            weightage_pct=20.0,
            recurrence_rate=0.5,
            trend_slope=None,
        ),
        _row(
            concept_id="3",
            label="Middle",
            weightage_pct=10.0,
            recurrence_rate=0.5,
            trend_slope=None,
        ),
    ]
    result = build_predictions(rows, top_n=2)
    assert result["top_n"] == 2
    assert [item["label"] for item in result["items"]] == ["Alpha", "Zebra"]
    assert [item["rank"] for item in result["items"]] == [1, 2]


def test_null_trend_does_not_raise_and_scores_zero_trend_term() -> None:
    rows = [
        _row(
            concept_id="x",
            label="Only",
            weightage_pct=40.0,
            recurrence_rate=1.0,
            trend_slope=None,
        )
    ]
    result = build_predictions(rows)
    assert len(result["items"]) == 1
    # 0.45*1 + 0.35*1 + 0.20*0 = 0.8
    assert result["items"][0]["score"] == 0.8
    assert "rising_trend" not in result["items"][0]["reasons"]


def test_unit_rows_from_syllabus_primary_score_and_rank() -> None:
    syllabus = {
        "summary": {"paper_count": 3},
        "units": [
            {"unit": "Unit I", "subpart_pct": 40.0, "subpart_count": 40},
            {"unit": "Unit II", "subpart_pct": 20.0, "subpart_count": 20},
            {"unit": "Unit III", "subpart_pct": 10.0, "subpart_count": 10},
        ],
        "year_unit_matrix": {
            "2021": {"Unit I": 5, "Unit II": 2, "Unit III": 0},
            "2022": {"Unit I": 8, "Unit II": 4, "Unit III": 1},
            "2023": {"Unit I": 12, "Unit II": 6, "Unit III": 2},
        },
        "top_topics": [
            {"name": "Electrochemistry", "count": 20, "pct": 20.0},
            {"name": "Water", "count": 10, "pct": 10.0},
        ],
    }
    unit_rows = unit_rows_from_syllabus_primary(syllabus)
    assert len(unit_rows) == 3
    assert unit_rows[0]["label"] == "Unit I"
    assert unit_rows[0]["recurrence_rate"] == 1.0  # present all 3 years

    result = build_predictions([], unit_rows=unit_rows, topic_rows=None)
    assert result["items"] == []
    assert [row["kind"] for row in result["units"]] == [KIND_UNIT] * 3
    assert result["units"][0]["label"] == "Unit I"
    assert result["units"][0]["rank"] == 1
    assert "high_weightage" in result["units"][0]["reasons"]


def test_attach_unit_predictions_prefers_structure_for_concept_id() -> None:
    base = empty_predictions()
    syllabus = {
        "summary": {"paper_count": 1},
        "units": [{"unit": "Unit A", "subpart_pct": 50.0, "subpart_count": 5}],
        "year_unit_matrix": {"2023": {"Unit A": 5}},
        "top_topics": [{"name": "Topic A", "count": 5, "pct": 50.0}],
    }
    structure = {
        "units": [
            {
                "unit_id": "u1",
                "title": "Unit A",
                "weightage_pct": 55.0,
                "recurrence_rate": 1.0,
                "mapped_concept_ids": ["concept-abc"],
            }
        ]
    }
    enriched = attach_unit_predictions(base, syllabus_block=syllabus, structure=structure)
    assert len(enriched["units"]) == 1
    assert enriched["units"][0]["kind"] == KIND_UNIT
    assert enriched["units"][0]["concept_id"] == "concept-abc"
    assert enriched["units"][0]["unit_id"] == "u1"
    assert len(enriched["topics"]) == 1
    assert enriched["topics"][0]["kind"] == KIND_TOPIC
    assert enriched["topics"][0]["label"] == "Topic A"


def test_unit_rows_from_structure_maps_first_concept() -> None:
    rows = unit_rows_from_structure(
        {
            "units": [
                {
                    "unit_id": "uid",
                    "title": "Polymers",
                    "weightage_pct": 12.0,
                    "recurrence_rate": 0.5,
                    "mapped_concept_ids": ["c1", "c2"],
                }
            ]
        }
    )
    assert rows[0]["concept_id"] == "c1"
    assert rows[0]["label"] == "Polymers"
