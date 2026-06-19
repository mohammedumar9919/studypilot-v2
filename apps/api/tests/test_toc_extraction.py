"""Tests for PDF TOC extraction and chapter rollup (Wave 6.6–6.7, SP-037–038)."""

from __future__ import annotations

from pathlib import Path

from app.services.pdf_extract import (
    PageText,
    _build_raw_outline_from_parsed,
    _finish_extracted_outline,
    _is_chapter_marker,
    _parse_engineering_syllabus_structure,
    extract_outline_from_pdf,
    extract_outline_from_text_toc,
    is_page_bucket_outline,
    normalize_outline_chapters,
    parse_outline_data,
    validate_extracted_outline,
)


def _flat_chemistry_eight_chapters() -> tuple[object, list[tuple[int, str, int]]]:
    parsed: list[tuple[int, str, int]] = []
    page = 0
    for chapter in range(1, 9):
        parsed.append((1, f"Chapter {chapter} Thermodynamics {chapter}", page))
        page += 2
        for subtopic in range(1, 6):
            parsed.append((1, f"Subtopic {chapter}.{subtopic}", page))
            page += 1
    page_count = page + 10
    raw = _build_raw_outline_from_parsed(parsed, page_count=page_count, document="Chemistry notes.pdf")
    return raw, parsed


def _syllabus_contents_no_page_numbers_pages() -> list[PageText]:
    contents = """CONTENTS

UNIT 1 Electrochemistry
1.1 ELECTROCHEMISTRY
1.2 ELECTROCHEMICAL CELLS
UNIT 2 Atomic Structure
2.1 ATOMIC MODELS
2.2 QUANTUM NUMBERS
UNIT 3 Chemical Bonding
3.1 IONIC BONDING
UNIT 4 Equilibrium
4.1 LE CHATELIER
UNIT 5 Organic Chemistry
5.1 HYDROCARBONS
"""
    pages: list[PageText] = [
        PageText(page=1, text="Chemistry Notes", char_count=15),
        PageText(page=2, text=contents, char_count=len(contents)),
    ]
    for page_num, heading in (
        (6, "UNIT 1.1 ELECTROCHEMISTRY"),
        (13, "UNIT 1.2 ELECTROCHEMICAL CELLS"),
        (26, "UNIT 2.1 ATOMIC MODELS"),
        (35, "UNIT 3.1 IONIC BONDING"),
        (45, "UNIT 4.1 LE CHATELIER"),
        (55, "UNIT 5.1 HYDROCARBONS"),
    ):
        body = f"{heading}\n\nDetailed notes for this section."
        pages.append(PageText(page=page_num, text=body, char_count=len(body)))
    return pages


def _syllabus_five_unit_toc_pages(*, page_count: int = 80) -> list[PageText]:
    toc_text = """Table of Contents

Unit 1 Thermodynamics ................ 1
Unit 2 Atomic Structure .............. 12
Unit 3 Chemical Bonding .............. 25
Unit 4 Equilibrium ................... 38
Unit 5 Electrochemistry .............. 52
"""
    return [PageText(page=1, text=toc_text, char_count=len(toc_text))]


def _flat_chemistry_bookmarks() -> tuple[object, list[tuple[int, str, int]]]:
    parsed: list[tuple[int, str, int]] = []
    page = 0
    for chapter in range(1, 6):
        parsed.append((1, f"Chapter {chapter} Thermodynamics {chapter}", page))
        page += 2
        for subtopic in range(1, 11):
            parsed.append((1, f"Subtopic {chapter}.{subtopic}", page))
            page += 1
    page_count = page + 10
    raw = _build_raw_outline_from_parsed(parsed, page_count=page_count, document="Chemistry notes.pdf")
    return raw, parsed


def test_chapter_marker_detection() -> None:
    assert _is_chapter_marker("Chapter 1 Introduction")
    assert _is_chapter_marker("UNIT 2 Alkanes")
    assert _is_chapter_marker("1. Atomic Structure")
    assert not _is_chapter_marker("Subtopic 1.3")
    assert not _is_chapter_marker("UNIT 1.1 ELECTROCHEMISTRY")


def test_flat_bookmarks_roll_up_to_five_chapters() -> None:
    raw, parsed = _flat_chemistry_bookmarks()
    assert len(raw.units) == 55

    normalized, granularity = normalize_outline_chapters(raw, toc_entries=parsed)
    assert normalized is not None
    assert granularity == "chapter"
    assert len(normalized.units) == 5
    assert all(len(unit.sections) == 10 for unit in normalized.units)
    assert "Thermodynamics" in normalized.units[0].title
    assert normalized.units[0].sections[0].title.startswith("Subtopic 1.")


def test_granular_flat_list_without_chapters_rejected() -> None:
    parsed = [(1, f"Slide {index}", index * 2) for index in range(50)]
    raw = _build_raw_outline_from_parsed(parsed, page_count=120, document="slides.pdf")

    normalized, granularity = normalize_outline_chapters(raw, toc_entries=parsed)
    assert normalized is None
    assert granularity is None


def test_syllabus_toc_yields_five_units() -> None:
    pages = _syllabus_five_unit_toc_pages()
    outline, granularity, quality = extract_outline_from_pdf(
        Path("__synthetic__.pdf"),
        pages=pages,
    )
    assert outline is not None
    assert granularity == "chapter"
    assert quality in ("high", "medium")
    assert len(outline.units) == 5
    assert outline.units[0].title.startswith("Unit 1")
    assert outline.units[4].title.startswith("Unit 5")


def _syllabus_spurious_same_page_toc_pages() -> list[PageText]:
    """Dotted TOC where units 1–4 share page 3 (CONTENTS page) — must use body anchors instead."""
    contents = """CONTENTS

Unit 1 Electrochemistry .... 3
1.1 ELECTROCHEMISTRY
1.2 ELECTROCHEMICAL CELLS
Unit 2 Atomic Structure .... 3
2.1 ATOMIC MODELS
Unit 3 Chemical Bonding .... 3
3.1 IONIC BONDING
Unit 4 Equilibrium .... 3
4.1 LE CHATELIER
Unit 5 Organic Chemistry .... 16
5.1 HYDROCARBONS
"""
    pages: list[PageText] = [
        PageText(page=1, text="Engineering Chemistry", char_count=20),
        PageText(page=2, text="blank", char_count=5),
        PageText(page=3, text=contents, char_count=len(contents)),
    ]
    for page_num, heading in (
        (6, "UNIT 1.1 ELECTROCHEMISTRY"),
        (13, "UNIT 1.2 ELECTROCHEMICAL CELLS"),
        (26, "UNIT 2.1 ATOMIC MODELS"),
        (35, "UNIT 3.1 IONIC BONDING"),
        (45, "UNIT 4.1 LE CHATELIER"),
        (55, "UNIT 5.1 HYDROCARBONS"),
    ):
        body = f"{heading}\n\nSection body text."
        pages.append(PageText(page=page_num, text=body, char_count=len(body)))
    return pages


def test_spurious_toc_page_numbers_use_body_anchors() -> None:
    pages = _syllabus_spurious_same_page_toc_pages()
    outline, granularity, _quality = extract_outline_from_pdf(
        Path("__synthetic__.pdf"),
        pages=pages,
    )
    assert outline is not None
    assert granularity == "chapter"
    assert len(outline.units) == 5
    assert "electrochemistry" in outline.units[0].title.lower()
    # Unit 1 must not be pinned to CONTENTS page 3 (0-based index 2).
    assert outline.units[0].page_start >= 4
    assert outline.units[0].page_end > outline.units[0].page_start
    assert len(outline.units[0].sections) >= 2
    assert any("1.1" in section.title for section in outline.units[0].sections)
    assert outline.units[1].page_start > outline.units[0].page_start
    assert outline.units[4].page_start > outline.units[0].page_start


def _engineering_chemistry_sparse_three_units_pages() -> list[PageText]:
    """
    CONTENTS lists units 1–5; body only has UNIT 1/2/5 major headings.
    Subsections 3.x/4.x belong under unit 2 (mis-numbered body headings).
    """
    contents = """CONTENTS

UNIT 1 Electrochemistry
1.1 ELECTROCHEMISTRY
1.2 BATTERY CHEMISTRY
UNIT 2 Water Chemistry
2.1 WATER CHEMISTRY
2.2 CORROSION
2.2 CORROSION CONTROL METHODS
2.4 SURFACE COATING METHODS
UNIT 3 Engineering Materials
3.1 ENGINEERING MATERIALS
UNIT 4 Chemical Fuels
4.1 CHEMICAL FUELS
UNIT 5 Green Chemistry
5.1 GREEN CHEMISTRY
5.2 COMPOSITES
"""
    pages: list[PageText] = [
        PageText(page=1, text="Engineering Chemistry", char_count=20),
        PageText(page=2, text="blank", char_count=5),
        PageText(page=3, text=contents, char_count=len(contents)),
    ]
    body_pages: list[tuple[int, str]] = [
        (4, "UNIT 1\n1.1 ELECTROCHEMISTRY"),
        (21, "1.2 BATTERY CHEMISTRY"),
        (27, "UNIT 2\n2.1 WATER CHEMISTRY"),
        (37, "3.1 ENGINEERING MATERIALS"),
        (46, "2.2 CORROSION"),
        (47, "4.1 CHEMICAL FUELS"),
        (53, "2.2 CORROSION CONTROL METHODS"),
        (55, "2.4 SURFACE COATING METHODS"),
        (57, "UNIT 5\n5.1 GREEN CHEMISTRY"),
        (62, "5.2 COMPOSITES"),
        (30, "2.303 x 8.314 x 303"),
        (58, "0.0591 [0.05]"),
    ]
    for page_num, text in body_pages:
        pages.append(PageText(page=page_num, text=text, char_count=len(text)))
    return pages


def test_sparse_three_chapter_pdf_rolls_up_units_1_2_5() -> None:
    pages = _engineering_chemistry_sparse_three_units_pages()
    outline, granularity, _quality = extract_outline_from_pdf(
        Path("__synthetic__.pdf"),
        pages=pages,
    )
    assert outline is not None
    assert granularity == "chapter"
    assert len(outline.units) == 3
    assert outline.units[0].page_start == 3
    assert outline.units[1].page_start == 26
    assert outline.units[2].page_start == 56
    unit1_titles = [section.title.upper() for section in outline.units[0].sections]
    assert any("1.1" in title for title in unit1_titles)
    assert any("1.2" in title for title in unit1_titles)
    unit2_titles = [section.title.upper() for section in outline.units[1].sections]
    assert any("2.1" in title for title in unit2_titles)
    assert any("CORROSION" in title for title in unit2_titles)
    assert any("2.4" in title or "SURFACE" in title for title in unit2_titles)
    assert not any("2.303" in title for title in unit2_titles)
    unit5_titles = [section.title.upper() for section in outline.units[2].sections]
    assert any("5.1" in title for title in unit5_titles)
    assert any("5.2" in title for title in unit5_titles)
    assert not any("0.0591" in title for title in unit5_titles)


def test_math_decimal_line_not_subsection_heading() -> None:
    from app.services.pdf_extract import _parse_subsection_heading_line

    assert _parse_subsection_heading_line("2.303 x 8.314 x 303") is None
    assert _parse_subsection_heading_line("2.4 SURFACE COATING METHODS") is not None
    assert _parse_subsection_heading_line("1.1 ELECTROCHEMISTRY") is not None


def test_unit_spans_are_non_overlapping() -> None:
    pages = _syllabus_spurious_same_page_toc_pages()
    outline, _, _ = extract_outline_from_pdf(Path("__synthetic__.pdf"), pages=pages)
    assert outline is not None
    for index in range(len(outline.units) - 1):
        assert outline.units[index].page_end < outline.units[index + 1].page_start


def test_contents_page_subsections_do_not_poison_body_anchors() -> None:
    """CONTENTS on page 3 lists 1.1/1.2; body anchors must come from later pages only."""
    from app.services.pdf_extract import _scan_body_subunit_anchors

    pages = _syllabus_spurious_same_page_toc_pages()
    anchors = _scan_body_subunit_anchors(pages)
    assert anchors[1] >= 4
    assert anchors[2] >= 20


def test_syllabus_contents_without_page_numbers_five_units() -> None:
    pages = _syllabus_contents_no_page_numbers_pages()
    outline, granularity, quality = extract_outline_from_pdf(
        Path("__synthetic__.pdf"),
        pages=pages,
    )
    assert outline is not None
    assert granularity == "chapter"
    assert quality in ("high", "medium")
    assert len(outline.units) == 5
    first_title = outline.units[0].title.lower()
    assert "electrochemistry" in first_title or first_title.startswith("unit 1")
    unit_one_sections = outline.units[0].sections
    assert any("1.1" in section.title for section in unit_one_sections)


def test_subunit_headings_roll_up_not_eight_top_level_units() -> None:
    parsed: list[tuple[int, str, int]] = []
    page = 10
    for major in range(1, 6):
        for sub in range(1, 3):
            parsed.append((1, f"UNIT {major}.{sub} TOPIC {major}.{sub}", page))
            page += 3
    raw = _build_raw_outline_from_parsed(parsed, page_count=80, document="Chemistry notes.pdf")
    assert len(raw.units) == 10

    pages = _syllabus_contents_no_page_numbers_pages()
    finished, granularity, quality = _finish_extracted_outline(raw, parsed, pages=pages)
    assert finished is not None
    assert granularity == "chapter"
    assert quality in ("high", "medium")
    assert len(finished.units) <= 5


def test_eight_chapter_bookmarks_merge_to_five_syllabus_units() -> None:
    raw, parsed = _flat_chemistry_eight_chapters()
    assert len(raw.units) == 48

    pages = _syllabus_five_unit_toc_pages(page_count=raw.page_count)
    finished, granularity, quality = _finish_extracted_outline(raw, parsed, pages=pages)
    assert finished is not None
    assert granularity == "chapter"
    assert quality in ("high", "medium")
    assert len(finished.units) == 5
    assert finished.units[0].title.startswith("Unit 1")
    assert finished.units[0].page_end >= finished.units[0].page_start + 5
    assert any("Subtopic" in section.title for unit in finished.units for section in unit.sections)


def test_toc_text_parse() -> None:
    toc_text = """Table of Contents

Chapter 1 Introduction ................ 1
Chapter 2 Alkanes ...................... 12
Chapter 3 Alkenes ...................... 24
"""
    pages = [PageText(page=1, text=toc_text, char_count=len(toc_text))]
    outline = extract_outline_from_text_toc(pages)

    assert outline is not None
    assert len(outline.units) >= 3
    titles = [section.title for unit in outline.units for section in unit.sections]
    unit_titles = [unit.title for unit in outline.units]
    assert "Alkanes" in titles or any("Alkanes" in title for title in unit_titles)
    assert not any("pages 1" in title for title in titles)


def test_validate_rejects_page_bucket_outline() -> None:
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
    assert is_page_bucket_outline(outline)
    assert validate_extracted_outline(outline) is False


def test_validate_accepts_real_section_titles() -> None:
    outline = parse_outline_data(
        {
            "document": "notes.pdf",
            "page_index_base": 0,
            "page_count": 20,
            "units": [
                {
                    "id": "1",
                    "title": "Organic Chemistry",
                    "page_start": 0,
                    "page_end": 19,
                    "sections": [
                        {"title": "Alkanes", "page_start": 0, "page_end": 9},
                        {"title": "Alkenes", "page_start": 10, "page_end": 19},
                    ],
                }
            ],
        }
    )
    assert validate_extracted_outline(outline) is True


CN_ENGINEERING_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "syllabus" / "cn_engineering_roman_units.txt"
)
CN_ENGINEERING_LIVE_SHAPE_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "syllabus" / "cn_engineering_live_shape.txt"
)
DATASCIENCE_SYLLABUS_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "syllabus" / "datascience_syllabus.txt"
)


def _cn_engineering_syllabus_pages() -> list[PageText]:
    text = CN_ENGINEERING_FIXTURE.read_text(encoding="utf-8")
    split_at = text.index("UNIT - III")
    page_one = text[:split_at].strip()
    page_two = text[split_at:].strip()
    return [
        PageText(page=1, text=page_one, char_count=len(page_one)),
        PageText(page=2, text=page_two, char_count=len(page_two)),
    ]


def _cn_engineering_live_shape_pages() -> list[PageText]:
    text = CN_ENGINEERING_LIVE_SHAPE_FIXTURE.read_text(encoding="utf-8")
    split_at = text.index("UNIT - III")
    page_one = text[:split_at].strip()
    page_two = text[split_at:].strip()
    return [
        PageText(page=1, text=page_one, char_count=len(page_one)),
        PageText(page=2, text=page_two, char_count=len(page_two)),
    ]


def test_indian_engineering_syllabus_live_shape_parts() -> None:
    pages = _cn_engineering_live_shape_pages()
    units = _parse_engineering_syllabus_structure(pages)
    assert len(units) == 5
    titles = [unit["unit_title"] for unit in units]
    assert len(set(titles)) == 5
    assert all(title.lower().startswith("unit ") for title in titles)

    part_counts = [len(unit["parts"]) for unit in units if unit.get("parts")]
    assert part_counts == [2, 3, 4, 2, 2]

    unit_one_part_one = units[0]["parts"][0]["subtopic_titles"]
    joined_part_one = " | ".join(unit_one_part_one).lower()
    assert any("flow of networks" in topic for topic in joined_part_one.split(" | "))
    assert any("william stalling" in topic.lower() for topic in unit_one_part_one)
    assert any("frequency division" in topic.lower() for topic in unit_one_part_one)
    assert not any(topic.strip().lower() == "flow of" for topic in unit_one_part_one)


def test_indian_engineering_syllabus_roman_units() -> None:
    pages = _cn_engineering_syllabus_pages()
    units = _parse_engineering_syllabus_structure(pages)
    assert len(units) == 5
    titles = [unit["unit_title"] for unit in units]
    assert len(set(titles)) == 5
    joined = " ".join(title.lower() for title in titles)
    assert "transport layer" in joined
    assert "application layer" in joined
    assert all(unit["subtopic_titles"] for unit in units)
    assert all(len(topic) >= 12 for unit in units for topic in unit["subtopic_titles"])
    assert all(len(unit["subtopic_titles"]) <= 8 for unit in units)


def test_engineering_syllabus_inline_dhcp_continuation() -> None:
    text = """UNIT - I Network Foundations

Physical layer concepts and transmission media overview.

UNIT - III Network Layer and Routing

Internet control protocols:
ARP, RARP, BOOTP and.
DHCP.Network Routing Algorithms: Delivery, Forwarding and Unicast Routing protocol, Gateway protocols

Routing Algorithms:
Distance vector routing, link state routing, hierarchical routing schemes
"""
    pages = [PageText(page=1, text=text, char_count=len(text))]
    units = _parse_engineering_syllabus_structure(pages)
    assert len(units) == 2
    parts = units[1]["parts"]
    assert len(parts) == 2
    icp = parts[0]
    assert icp["part_title"] == "Internet control protocols"
    joined_topics = " ".join(icp["subtopic_titles"]).lower()
    assert "arp" in joined_topics
    assert "bootp" in joined_topics
    assert "dhcp" in joined_topics
    assert "delivery" in joined_topics
    assert not any(part["part_title"].startswith("DHCP") for part in parts)


CN_ENGINEERING_LIVE_PDF = Path(
    r"C:\Users\Owner\Downloads\WhatsApp Unknown 2026-06-09 at 2.11.11 AM\CN syllabus.pdf"
)


def test_live_cn_syllabus_pdf() -> None:
    if not CN_ENGINEERING_LIVE_PDF.is_file():
        return
    from app.services.pdf_extract import extract_pdf

    result = extract_pdf(CN_ENGINEERING_LIVE_PDF)
    units = _parse_engineering_syllabus_structure(result.pages)
    assert len(units) == 5
    part_counts = [len(unit["parts"]) for unit in units if unit.get("parts")]
    assert part_counts == [2, 3, 4, 2, 2]
    unit_one_part_one = units[0]["parts"][0]["subtopic_titles"]
    assert any("william stalling" in topic.lower() for topic in unit_one_part_one)


def test_engineering_syllabus_structure_returns_empty_on_parse_fail() -> None:
    pages = [PageText(page=1, text="Course overview\nNo unit headers.", char_count=35)]
    assert _parse_engineering_syllabus_structure(pages) == []


def test_engineering_syllabus_structure_supports_arabic_unit_header() -> None:
    text = """Unit 1 Network Foundations

Physical layer concepts and transmission media overview.

Unit 2 Data Link Layer

Framing techniques and error detection methods.
"""
    pages = [PageText(page=1, text=text, char_count=len(text))]
    units = _parse_engineering_syllabus_structure(pages)
    assert len(units) == 2
    assert units[0]["unit_title"].startswith("Unit 1")
    assert units[1]["unit_title"].startswith("Unit 2")
    assert len(units[0]["subtopic_titles"]) >= 1


def test_indian_engineering_syllabus_roman_units_no_pages() -> None:
    pages = _cn_engineering_syllabus_pages()
    outline, granularity, quality = extract_outline_from_pdf(
        Path("__synthetic__.pdf"),
        pages=pages,
    )
    assert outline is not None
    assert outline.extraction_method == "syllabus_block"
    assert granularity == "chapter"
    assert quality == "medium"
    assert len(outline.units) == 5
    titles = " ".join(unit.title.lower() for unit in outline.units)
    assert "transport layer" in titles
    assert "application layer" in titles
    assert all(unit.sections for unit in outline.units)
    assert outline.units[0].page_start == 0
    assert outline.units[4].page_start == 4
    assert all(section.page_start == unit.page_start for unit in outline.units for section in unit.sections)


def test_datascience_syllabus_modular_depth() -> None:
    text = DATASCIENCE_SYLLABUS_FIXTURE.read_text(encoding="utf-8")
    pages = [PageText(page=1, text=text, char_count=len(text))]
    units = _parse_engineering_syllabus_structure(pages)
    assert len(units) == 5

    unit_two = units[1]
    assert not unit_two.get("parts")
    assert len(unit_two["subtopic_titles"]) >= 6
    joined_u2 = " ".join(unit_two["subtopic_titles"]).lower()
    assert "statistical modeling" in joined_u2
    assert "hypothesis testing" in joined_u2
    assert not any("statisti hypothesis" in topic.lower() for topic in unit_two["subtopic_titles"])

    unit_three = units[2]
    assert unit_three.get("parts")
    assert len(unit_three["parts"]) == 1
    assert unit_three["parts"][0]["part_title"] == "Predictive Modeling"
    part_titles_u3 = [part["part_title"] for part in unit_three.get("parts", [])]
    assert not any("inference" in title.lower() for title in part_titles_u3)

    unit_four = units[3]
    assert unit_four.get("parts")
    part_titles_u4 = [part["part_title"] for part in unit_four["parts"]]
    assert any("operations" in title.lower() for title in part_titles_u4)

    unit_five = units[4]
    assert unit_five.get("parts")
    assert len(unit_five["parts"]) == 2
    part_titles_u5 = [part["part_title"] for part in unit_five["parts"]]
    assert any("classification" in title.lower() for title in part_titles_u5)
    assert any("clustering" in title.lower() for title in part_titles_u5)


def test_engineering_syllabus_ocr_unit_repair() -> None:
    text = """UNIT - I Network Foundations

Topics on physical and data link layers.

UNIT - I Data Link Control

Medium access and framing topics.

UNIT - I Network Layer Routing

Routing and IP addressing topics.

UNIT - I Transport Layer

TCP UDP and flow control topics.

UNIT - I Application Layer

HTTP DNS and application security topics.
"""
    pages = [PageText(page=1, text=text, char_count=len(text))]
    outline, _granularity, quality = extract_outline_from_pdf(Path("__synthetic__.pdf"), pages=pages)
    assert outline is not None
    assert quality == "medium"
    assert len(outline.units) == 5
    joined = " ".join(unit.title.lower() for unit in outline.units)
    assert "transport" in joined
    assert "application" in joined
