from pathlib import Path

from app.services.chunker.base import DOC_KIND_SPECS, estimate_tokens
from app.services.chunker.hierarchical import chunk_pages
from app.services.pdf_extract import PageText, load_outline, resolve_page_metadata


def test_estimate_tokens() -> None:
    assert estimate_tokens("one two three") == 3


def test_chunk_notes_pages() -> None:
    pages = [
        PageText(page=1, text="Unit 1 " * 200, char_count=1400),
        PageText(page=2, text="Unit 1 continued " * 200, char_count=1600),
    ]
    result = chunk_pages(pages, "notes")
    assert len(result.parents) >= 1
    assert len(result.children) >= 1
    assert result.children[0].page == 1


def test_past_paper_page_level_chunks() -> None:
    pages = [PageText(page=3, text="Question 1: What is BNF?\nQuestion 2: EBNF?" * 20, char_count=500)]
    result = chunk_pages(pages, "past_paper")
    assert len(result.parents) == 1
    assert result.parents[0].page_start == 3
    assert len(result.children) >= 1


def test_doc_kind_specs_exist() -> None:
    assert "notes" in DOC_KIND_SPECS
    assert "past_paper" in DOC_KIND_SPECS


def test_chunk_pages_preserves_section_metadata_without_forcing_parent_splits() -> None:
    pages = [
        PageText(
            page=4,
            text="unit one " * 50,
            char_count=450,
            metadata={"unit": "1", "section_title": "Preliminary Concepts", "toc_path": "Unit 1 > Preliminary Concepts"},
        ),
        PageText(
            page=5,
            text="unit one cont " * 50,
            char_count=650,
            metadata={"unit": "1", "section_title": "Syntax and Semantics", "toc_path": "Unit 1 > Syntax and Semantics"},
        ),
    ]
    result = chunk_pages(pages, "notes")
    assert len(result.parents) == 1
    assert result.parents[0].metadata.get("unit") == "1"
    assert result.children[0].metadata.get("toc_path") == "Unit 1 > Preliminary Concepts"


def test_ppl_outline_resolves_golden_page_metadata() -> None:
    outline_path = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml"
    outline = load_outline(outline_path)

    meta = resolve_page_metadata(outline, 11)
    assert meta["unit"] == "1"
    assert meta["section_title"] == "Syntax and Semantics"
    assert meta["toc_path"] == "Unit 1 > Syntax and Semantics"

    meta_u5 = resolve_page_metadata(outline, 86)
    assert meta_u5["unit"] == "5"
    assert "Functional Programming" in meta_u5["section_title"]
