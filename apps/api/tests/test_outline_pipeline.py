"""Tests for Wave 7 universal outline pipeline (SP-039)."""

from __future__ import annotations

from app.services.outline_hints import (
    build_section_page_hints_from_outline,
    build_unit_phrases_from_outline,
)
from app.services.pdf_extract import (
    OutlineSection,
    OutlineUnit,
    DocumentOutline,
    normalize_outline,
    outline_quality_score,
    parse_outline_data,
)
from app.services.rag.retrieve import infer_unit_hints, retrieval_course_context, section_page_hints


def _chemistry_outline() -> DocumentOutline:
    return parse_outline_data(
        {
            "document": "Chemistry notes.pdf",
            "page_index_base": 0,
            "page_count": 100,
            "units": [
                {
                    "id": "1",
                    "title": "Thermodynamics",
                    "page_start": 0,
                    "page_end": 19,
                    "sections": [
                        {"title": "Alkanes", "page_start": 0, "page_end": 9},
                        {"title": "Enthalpy", "page_start": 10, "page_end": 19},
                    ],
                },
                {
                    "id": "2",
                    "title": "Kinetics",
                    "page_start": 20,
                    "page_end": 39,
                    "sections": [
                        {"title": "Reaction rates", "page_start": 20, "page_end": 29},
                        {"title": "Catalysts", "page_start": 30, "page_end": 39},
                    ],
                },
            ],
        }
    )


def test_normalize_outline_merges_short_sections() -> None:
    outline = DocumentOutline(
        document="notes.pdf",
        course="X",
        page_index_base=0,
        page_count=20,
        units=[
            OutlineUnit(
                id="1",
                title="Unit 1",
                page_start=0,
                page_end=19,
                sections=[
                    OutlineSection(title="A", page_start=0, page_end=1),
                    OutlineSection(title="B", page_start=2, page_end=10),
                ],
            )
        ],
    )
    normalized, granularity = normalize_outline(outline)
    assert granularity in ("chapter", "section")
    assert normalized.units[0].sections[0].page_end >= 1


def test_outline_quality_high_for_chapter_outline() -> None:
    outline = parse_outline_data(
        {
            "document": "notes.pdf",
            "page_index_base": 0,
            "page_count": 100,
            "units": [
                {
                    "id": str(index),
                    "title": f"Chapter {index}",
                    "page_start": (index - 1) * 20,
                    "page_end": index * 20 - 1,
                    "sections": [
                        {"title": f"Topic {index}A", "page_start": (index - 1) * 20, "page_end": (index - 1) * 20 + 9},
                        {"title": f"Topic {index}B", "page_start": (index - 1) * 20 + 10, "page_end": index * 20 - 1},
                    ],
                }
                for index in range(1, 4)
            ],
        }
    )
    assert outline_quality_score(outline, "chapter") == "high"


def test_outline_quality_low_for_page_stub() -> None:
    outline = parse_outline_data(
        {
            "document": "notes.pdf",
            "page_index_base": 0,
            "page_count": 20,
            "units": [
                {
                    "id": "1",
                    "title": "notes",
                    "page_start": 0,
                    "page_end": 19,
                    "sections": [
                        {"title": "notes — pages 1–10", "page_start": 0, "page_end": 9},
                        {"title": "notes — pages 11–20", "page_start": 10, "page_end": 19},
                    ],
                }
            ],
        }
    )
    assert outline_quality_score(outline, "page_stub", is_auto_stub=True) == "low"


def test_dynamic_hints_from_outline() -> None:
    outline = _chemistry_outline()
    phrases = build_unit_phrases_from_outline(outline)
    hints = build_section_page_hints_from_outline(outline)
    assert "alkanes" in phrases["1"]
    assert any(row[0] == "alkanes" for row in hints)


def test_infer_unit_hints_generic_course() -> None:
    outline = _chemistry_outline()
    from app.services.rag import retrieve as retrieve_module

    retrieve_module._dynamic_hints_cache["CHEM"] = (
        build_unit_phrases_from_outline(outline),
        {},
        build_section_page_hints_from_outline(outline),
    )
    with retrieval_course_context("CHEM"):
        hints = infer_unit_hints("Explain alkanes and enthalpy changes")
    assert hints and hints[0] == "1"
