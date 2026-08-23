"""PyMuPDF text extraction with optional Tesseract OCR fallback."""

from __future__ import annotations

import logging
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

import fitz
import yaml

from app.config import settings

logger = logging.getLogger(__name__)

OutlineStorageSource = Literal["extracted", "uploaded"]
OutlineGranularity = Literal["chapter", "section", "page_stub"]
OutlineQuality = Literal["high", "medium", "low"]

_TOC_HEADING_RE = re.compile(r"table\s+of\s+contents|^contents\s*$", re.I | re.M)
_TOC_DOTS_LINE_RE = re.compile(r"^(.+?)\s+\.{2,}\s*(\d+)\s*$")
_TOC_CHAPTER_LINE_RE = re.compile(
    r"^(?:(?:chapter|unit|section|part)\s*)?[\d.]+\s*(.+?)\s+\.{2,}\s*(\d+)\s*$",
    re.I,
)
_SYLLABUS_UNIT_LINE_RE = re.compile(
    r"^unit\s+(\d+)\s+(.+?)\s+\.{2,}\s*(\d+)\s*$",
    re.I,
)
_SYLLABUS_NUMBERED_UNIT_LINE_RE = re.compile(
    r"^(\d+)\.\s+([A-Z][^.]*?)\s+\.{2,}\s*(\d+)\s*$",
)
_PAGE_BUCKET_TITLE_RE = re.compile(r"^.+\s+pages\s+\d+\s*[–-]\s*\d+$", re.I)
_CHAPTER_MARKER_RE = re.compile(
    r"^(?:chapter|unit|module|part)\s+(?:[0-9]+|[IVXLCDM]+)\b",
    re.I,
)
_NUMBERED_CHAPTER_RE = re.compile(r"^(\d+)[.\s]\s+\S")
_CHAPTER_PREFIX_STRIP_RE = re.compile(
    r"^(?:chapter|unit|module|part)\s+(?:[0-9]+|[IVXLCDM]+)\s*[:.\-–]?\s*",
    re.I,
)
_TEXT_TOC_MAX_PAGES = 15
_MAX_SECTIONS_WITHOUT_CHAPTER = 30
_MAX_SECTIONS_CAP = 30
_MAX_UNITS_CAP = 12
_MIN_UNIT_COUNT = 3
_MIN_SECTION_SPAN = 3
_NUMBERED_HEADING_RE = re.compile(
    r"^(?:(?:chapter|unit|module|part)\s+(?:[0-9]+|[IVXLCDM]+)|\d+(?:\.\d+)?)\s*[.:]?\s*(.+)$",
    re.I,
)
_SUBUNIT_HEADING_RE = re.compile(r"^unit\s+(\d+)\.(\d+)\b", re.I)
_SYLLABUS_MAJOR_UNIT_NO_PAGE_RE = re.compile(
    r"^unit\s+(\d+)(?!\.)\s*(.*)$",
    re.I,
)
_SYLLABUS_SUBSECTION_NO_PAGE_RE = re.compile(r"^(\d+)\.(\d+)\s+(.+)$")
_MAJOR_UNIT_TITLE_RE = re.compile(r"^unit\s+(\d+)(?!\.)\b", re.I)
_SUBSECTION_NUMERIC_TITLE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?!\d)\s+(.+)$")
_SUBUNIT_IN_TEXT_RE = re.compile(r"\bunit\s+(\d+)\.(\d{1,2})\b(?!\d)", re.I)
_MATHY_SUBSECTION_RE = re.compile(r"\d+\s*[x×]\s*\d+|[\d.]+\s*[+\-*/]\s*[\d.]+", re.I)
_FORMULA_CONSTANT_RE = re.compile(r"^[\d.\[\]\s]+$|^0\.\d+[^A-Za-z\s]")
_MAJOR_UNIT_BODY_LINE_RE = re.compile(
    r"^unit\s+(\d+)(?!\.)\s*(?:[A-Za-z].*)?\s*$",
    re.I,
)
_MAX_SUBSECTION_MINOR = 50
_SYLLABUS_TOC_PAGE_SUFFIX_RE = re.compile(r"\.{2,}\s*\d+\s*$")
_SYLLABUS_SUBSECTION_TITLE_PARTS_RE = re.compile(r"^(\d+)\.(\d+)\s+(.+)$")
_ROMAN_NUMERAL_VALUES: dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
}
_ENGINEERING_UNIT_DASHED_RE = re.compile(
    r"^unit\s*[-–]\s*(?P<index>[IVXLCDM]+|\d+)\b\s*(?P<rest>.*)$",
    re.I,
)
_ENGINEERING_UNIT_HYPHEN_DIGIT_RE = re.compile(
    r"^unit\s*-(?P<index>\d+)\b\s*(?P<rest>.*)$",
    re.I,
)
_ENGINEERING_UNIT_ROMAN_RE = re.compile(
    r"^unit\s+(?P<index>[IVXLCDM]+)\b(?!\.\d)\s*(?P<rest>.*)$",
    re.I,
)
_ENGINEERING_UNIT_ARABIC_RE = re.compile(
    r"^unit\s+(?P<index>\d+)\b(?!\.\d)\s*(?P<rest>.*)$",
    re.I,
)
_ENGINEERING_FOOTER_READINGS_RE = re.compile(
    r"^(?:suggested\s+readings?|references)\s*:?\s*$",
    re.I,
)
_ENGINEERING_FOOTER_PROGRAM_RE = re.compile(
    r"^BE\s*\(\s*Computer\s+Science",
    re.I,
)
_ENGINEERING_EMBEDDED_PART_HEADING_RE = re.compile(
    r"(?<=[.,])\s*([A-Z][a-z]+(?:\s+[A-Za-z]+){0,7}):\s+",
)
_SPURIOUS_EMBEDDED_PART_WORDS = frozenset(
    {
        "analysis",
        "classification",
        "clustering",
        "estimation",
        "forecasting",
        "inference",
        "learning",
        "modeling",
        "optimization",
        "prediction",
        "regression",
        "statistical",
        "visualization",
    }
)


class EngineeringSyllabusPart(TypedDict):
    part_title: str
    subtopic_titles: list[str]


class EngineeringSyllabusUnit(TypedDict, total=False):
    unit_title: str
    subtopic_titles: list[str]
    parts: list[EngineeringSyllabusPart]


@dataclass
class PageText:
    page: int
    text: str
    char_count: int
    used_ocr: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    pages: list[PageText]
    page_count: int
    total_chars: int
    nonempty_pages: int
    ocr_pages: int
    quality_flags: dict


def _configure_tesseract() -> None:
    if shutil.which("tesseract"):
        return
    win_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if win_default.is_file():
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = str(win_default)
        return
    raise RuntimeError("OCR required but tesseract binary not found on PATH")


def _ocr_page(doc: fitz.Document, page_index: int) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "OCR required for scanned pages but pytesseract/Pillow not installed"
        ) from exc

    _configure_tesseract()

    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(img) or ""


def extract_pdf(path: Path, ocr_threshold: int | None = None) -> ExtractionResult:
    threshold = ocr_threshold if ocr_threshold is not None else settings.ocr_chars_per_page_threshold
    doc = fitz.open(path)
    pages: list[PageText] = []
    ocr_pages = 0

    for i in range(len(doc)):
        text = doc[i].get_text("text", sort=True) or ""
        used_ocr = False
        # <= so pages with junk native text exactly at threshold still get OCR (PYQ pp. 28–30).
        if len(text.strip()) <= threshold:
            try:
                ocr_text = _ocr_page(doc, i)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    used_ocr = True
                    ocr_pages += 1
            except RuntimeError as exc:
                logger.warning("OCR skipped for page %s: %s", i + 1, exc)
        pages.append(
            PageText(page=i + 1, text=text.strip(), char_count=len(text.strip()), used_ocr=used_ocr)
        )

    doc.close()
    total_chars = sum(p.char_count for p in pages)
    nonempty = sum(1 for p in pages if p.char_count > 0)

    quality_flags: dict = {
        "native_text_ratio": round(nonempty / max(len(pages), 1), 3),
        "ocr_page_count": ocr_pages,
        "avg_chars_per_page": round(total_chars / max(len(pages), 1), 1),
    }
    if nonempty == 0:
        quality_flags["needs_ocr"] = True
        quality_flags["partial"] = True
    elif ocr_pages > 0 and ocr_pages >= len(pages) // 2:
        quality_flags["needs_ocr"] = True
        quality_flags["partial"] = True
    elif ocr_pages > 0:
        quality_flags["partial"] = True

    return ExtractionResult(
        pages=pages,
        page_count=len(pages),
        total_chars=total_chars,
        nonempty_pages=nonempty,
        ocr_pages=ocr_pages,
        quality_flags=quality_flags,
    )


PdfAuditTier = Literal["native", "ocr", "layout_defer"]
_MAX_AUDIT_SAMPLE_PAGES = 12


@dataclass
class PdfAuditResult:
    tier: PdfAuditTier
    page_count: int
    sampled_pages: int
    native_empty_ratio: float
    multi_column_ratio: float
    image_heavy_ratio: float
    avg_native_chars: float

    def as_quality_fields(self) -> dict[str, Any]:
        return {
            "audit_tier": self.tier,
            "audit_page_count": self.page_count,
            "audit_sampled_pages": self.sampled_pages,
            "audit_native_empty_ratio": round(self.native_empty_ratio, 3),
            "audit_multi_column_ratio": round(self.multi_column_ratio, 3),
            "audit_image_heavy_ratio": round(self.image_heavy_ratio, 3),
            "audit_avg_native_chars": round(self.avg_native_chars, 1),
        }


def _sample_page_indices(page_count: int, *, max_pages: int = _MAX_AUDIT_SAMPLE_PAGES) -> list[int]:
    if page_count <= 0:
        return []
    if page_count <= max_pages:
        return list(range(page_count))
    step = max(1, page_count // max_pages)
    indices = list(range(0, page_count, step))
    if indices[-1] != page_count - 1:
        indices.append(page_count - 1)
    return indices[:max_pages]


def _text_block_x_centers(blocks: list[dict[str, Any]]) -> list[float]:
    centers: list[float] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        centers.append((float(bbox[0]) + float(bbox[2])) / 2)
    return centers


def _looks_multi_column(blocks: list[dict[str, Any]], page_width: float) -> bool:
    if page_width <= 0:
        return False
    centers = _text_block_x_centers(blocks)
    if len(centers) < 8:
        return False
    left = sum(1 for center in centers if center < page_width * 0.45)
    right = sum(1 for center in centers if center > page_width * 0.55)
    return left >= 3 and right >= 3


def classify_audit_tier(
    *,
    native_empty_ratio: float,
    multi_column_ratio: float,
    image_heavy_ratio: float,
) -> PdfAuditTier:
    """Route PDFs to native / OCR / layout-defer extraction paths (SP-045a)."""
    if native_empty_ratio >= 0.75 or image_heavy_ratio >= 0.75:
        return "ocr"
    if multi_column_ratio >= 0.35 and native_empty_ratio < 0.5:
        return "layout_defer"
    if native_empty_ratio >= 0.2 or image_heavy_ratio >= 0.35:
        return "ocr"
    return "native"


def reconcile_audit_tier(audit: PdfAuditResult, extraction: ExtractionResult) -> PdfAuditTier:
    page_count = max(extraction.page_count, 1)
    ocr_ratio = extraction.ocr_pages / page_count
    native_ratio = extraction.nonempty_pages / page_count

    if native_ratio == 0:
        return "ocr"
    if ocr_ratio >= 0.5:
        return "ocr"
    if audit.tier == "layout_defer":
        return "layout_defer"
    if ocr_ratio >= 0.15:
        return "ocr"
    if audit.tier == "native" and audit.multi_column_ratio >= 0.35:
        return "layout_defer"
    return audit.tier


def audit_pdf(path: Path, ocr_threshold: int | None = None) -> PdfAuditResult:
    """Lightweight pre-extract audit — no OCR, for ingest routing (SP-045a)."""
    threshold = ocr_threshold if ocr_threshold is not None else settings.ocr_chars_per_page_threshold
    doc = fitz.open(path)
    page_count = len(doc)
    sample_indices = _sample_page_indices(page_count)

    native_chars: list[int] = []
    multi_column_pages = 0
    image_heavy_pages = 0

    for index in sample_indices:
        page = doc[index]
        text = page.get_text("text", sort=True) or ""
        char_count = len(text.strip())
        native_chars.append(char_count)

        blocks = page.get_text("dict", sort=True).get("blocks", [])
        if _looks_multi_column(blocks, page.rect.width):
            multi_column_pages += 1

        if char_count <= threshold and page.get_images():
            image_heavy_pages += 1

    doc.close()

    sampled = max(len(sample_indices), 1)
    native_empty_ratio = sum(1 for count in native_chars if count <= threshold) / sampled
    return PdfAuditResult(
        tier=classify_audit_tier(
            native_empty_ratio=native_empty_ratio,
            multi_column_ratio=multi_column_pages / sampled,
            image_heavy_ratio=image_heavy_pages / sampled,
        ),
        page_count=page_count,
        sampled_pages=len(sample_indices),
        native_empty_ratio=native_empty_ratio,
        multi_column_ratio=multi_column_pages / sampled,
        image_heavy_ratio=image_heavy_pages / sampled,
        avg_native_chars=sum(native_chars) / sampled,
    )


@dataclass
class OutlineSection:
    title: str
    page_start: int
    page_end: int


@dataclass
class OutlineUnit:
    id: str
    title: str
    page_start: int
    page_end: int
    sections: list[OutlineSection]


@dataclass
class DocumentOutline:
    document: str
    course: str
    page_index_base: int
    page_count: int
    units: list[OutlineUnit]
    front_matter: OutlineSection | None = None
    extraction_method: str | None = None


def _parse_outline_section(raw: dict[str, Any]) -> OutlineSection:
    return OutlineSection(
        title=str(raw["title"]),
        page_start=int(raw["page_start"]),
        page_end=int(raw["page_end"]),
    )


def parse_outline_data(data: dict[str, Any]) -> DocumentOutline:
    """Parse outline dict (YAML JSON shape or DB-stored outline_data)."""
    front_matter = None
    if raw_front := data.get("front_matter"):
        front_matter = _parse_outline_section(raw_front)
    units = [
        OutlineUnit(
            id=str(unit["id"]),
            title=str(unit["title"]),
            page_start=int(unit["page_start"]),
            page_end=int(unit["page_end"]),
            sections=[_parse_outline_section(section) for section in unit.get("sections", [])],
        )
        for unit in data.get("units", [])
    ]
    return DocumentOutline(
        document=str(data.get("document", "")),
        course=str(data.get("course", "")),
        page_index_base=int(data.get("page_index_base", 0)),
        page_count=int(data.get("page_count", 0)),
        units=units,
        front_matter=front_matter,
    )


def load_outline(path: Path) -> DocumentOutline:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    outline = parse_outline_data(data)
    if not outline.document:
        outline = DocumentOutline(
            document=str(data.get("document", path.stem)),
            course=outline.course or str(data.get("course", "")),
            page_index_base=outline.page_index_base,
            page_count=outline.page_count,
            units=outline.units,
            front_matter=outline.front_matter,
        )
    return outline


def _page_in_range(page_index: int, start: int, end: int) -> bool:
    return start <= page_index <= end


def resolve_page_metadata(outline: DocumentOutline, page_index: int) -> dict[str, str | None]:
    if outline.front_matter and _page_in_range(
        page_index, outline.front_matter.page_start, outline.front_matter.page_end
    ):
        title = outline.front_matter.title
        return {
            "unit": None,
            "section_title": title,
            "toc_path": title,
        }

    for unit in outline.units:
        if not _page_in_range(page_index, unit.page_start, unit.page_end):
            continue
        unit_label = f"Unit {unit.id}"
        section_title = unit.title
        for section in unit.sections:
            if _page_in_range(page_index, section.page_start, section.page_end):
                section_title = section.title
                break
        return {
            "unit": unit.id,
            "section_title": section_title,
            "toc_path": f"{unit_label} > {section_title}",
        }

    return {"unit": None, "section_title": None, "toc_path": None}


def outline_summary(outline: DocumentOutline, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "document": outline.document,
        "course": outline.course,
        "page_index_base": outline.page_index_base,
        "unit_count": len(outline.units),
        "units": [
            {
                "id": unit.id,
                "title": unit.title,
                "page_start": unit.page_start,
                "page_end": unit.page_end,
                "sections": [
                    {
                        "title": section.title,
                        "page_start": section.page_start,
                        "page_end": section.page_end,
                    }
                    for section in unit.sections
                ],
            }
            for unit in outline.units
        ],
        "needs_human_review": True,
    }


def _extract_page_index(page: PageText) -> int:
    # Outline YAML uses 0-based PDF indices; extract_pdf stores 1-based page numbers.
    return page.page - 1


def annotate_pages_with_outline(pages: list[PageText], outline: DocumentOutline) -> None:
    for page in pages:
        page.metadata.update(resolve_page_metadata(outline, _extract_page_index(page)))


def _section_count(outline: DocumentOutline) -> int:
    return sum(len(unit.sections) for unit in outline.units)


def is_page_bucket_outline(outline: DocumentOutline) -> bool:
    """True when every section title looks like an auto-stub page bucket."""
    sections = [section for unit in outline.units for section in unit.sections]
    if not sections:
        return True
    return all(_PAGE_BUCKET_TITLE_RE.match(section.title) for section in sections)


def validate_extracted_outline(outline: DocumentOutline) -> bool:
    """Reject page-bucket stubs and outlines with fewer than two sections."""
    if _section_count(outline) < 2:
        return False
    if is_page_bucket_outline(outline):
        return False
    return True


def outline_to_storage_dict(
    outline: DocumentOutline,
    source: OutlineStorageSource,
    *,
    outline_granularity: OutlineGranularity | None = None,
    outline_quality: OutlineQuality | None = None,
) -> dict[str, Any]:
    """Serialize outline for Course.outline_data including outline_source."""
    payload: dict[str, Any] = {
        "document": outline.document,
        "course": outline.course,
        "page_index_base": outline.page_index_base,
        "page_count": outline.page_count,
        "outline_source": source,
        "units": [
            {
                "id": unit.id,
                "title": unit.title,
                "page_start": unit.page_start,
                "page_end": unit.page_end,
                "sections": [
                    {
                        "title": section.title,
                        "page_start": section.page_start,
                        "page_end": section.page_end,
                    }
                    for section in unit.sections
                ],
            }
            for unit in outline.units
        ],
    }
    if outline_granularity is not None:
        payload["outline_granularity"] = outline_granularity
    if outline_quality is not None:
        payload["outline_quality"] = outline_quality
    if outline.front_matter is not None:
        payload["front_matter"] = {
            "title": outline.front_matter.title,
            "page_start": outline.front_matter.page_start,
            "page_end": outline.front_matter.page_end,
        }
    return payload


def _finalize_unit_ranges(units: list[OutlineUnit]) -> None:
    for unit in units:
        if unit.sections:
            unit.page_start = min(section.page_start for section in unit.sections)
            unit.page_end = max(section.page_end for section in unit.sections)
        if not unit.sections:
            unit.sections.append(
                OutlineSection(
                    title=unit.title,
                    page_start=unit.page_start,
                    page_end=unit.page_end,
                )
            )


def _is_chapter_marker(title: str) -> bool:
    clean = title.strip()
    if _SUBUNIT_HEADING_RE.match(clean):
        return False
    if _CHAPTER_MARKER_RE.match(clean):
        return True
    return _NUMBERED_CHAPTER_RE.match(clean) is not None


def _page_index_from_page_text(page: PageText) -> int:
    """PageText.page is 1-based (see extract_pdf); outline indices are 0-based."""
    return max(0, page.page - 1)


def _major_unit_from_title(title: str) -> int | None:
    clean = title.strip()
    subunit = _SUBUNIT_HEADING_RE.match(clean)
    if subunit:
        return int(subunit.group(1))
    numbered = _SUBSECTION_NUMERIC_TITLE_RE.match(clean)
    if numbered:
        return int(numbered.group(1))
    major = _MAJOR_UNIT_TITLE_RE.match(clean)
    if major:
        return int(major.group(1))
    return None


def _clean_chapter_title(title: str) -> str:
    clean = title.strip()
    stripped = _CHAPTER_PREFIX_STRIP_RE.sub("", clean).strip()
    if stripped:
        return stripped
    numbered = _NUMBERED_CHAPTER_RE.sub(r"\1 ", "", clean).strip()
    return numbered or clean


def _compute_page_ends(parsed: list[tuple[int, str, int]], page_count: int) -> list[int]:
    page_ends: list[int] = []
    for index, (_level, _title, page_start) in enumerate(parsed):
        if index + 1 < len(parsed):
            page_end = max(page_start, parsed[index + 1][2] - 1)
        else:
            page_end = max(page_start, page_count - 1)
        page_ends.append(page_end)
    return page_ends


def _flatten_outline_entries(outline: DocumentOutline) -> list[tuple[str, int, int]]:
    entries: list[tuple[str, int, int]] = []
    if len(outline.units) == 1 and len(outline.units[0].sections) > 1:
        for section in outline.units[0].sections:
            entries.append((section.title, section.page_start, section.page_end))
    else:
        for unit in outline.units:
            if unit.sections and not (
                len(unit.sections) == 1 and unit.sections[0].title == unit.title
            ):
                for section in unit.sections:
                    entries.append((section.title, section.page_start, section.page_end))
            else:
                entries.append((unit.title, unit.page_start, unit.page_end))
    entries.sort(key=lambda item: (item[1], item[0]))
    return entries


def _too_granular_without_chapters(outline: DocumentOutline) -> bool:
    return _section_count(outline) > _MAX_SECTIONS_WITHOUT_CHAPTER and len(outline.units) > 12


def _clone_outline_with_units(outline: DocumentOutline, units: list[OutlineUnit]) -> DocumentOutline:
    return DocumentOutline(
        document=outline.document,
        course=outline.course,
        page_index_base=outline.page_index_base,
        page_count=outline.page_count,
        units=units,
        front_matter=outline.front_matter,
    )


def _rollup_flat_by_chapters(
    flat: list[tuple[str, int, int]],
    page_count: int,
    chapter_indices: list[int],
) -> list[OutlineUnit]:
    units: list[OutlineUnit] = []
    for unit_index, chapter_index in enumerate(chapter_indices):
        chapter_title, chapter_start, _ = flat[chapter_index]
        next_chapter_index = (
            chapter_indices[unit_index + 1] if unit_index + 1 < len(chapter_indices) else len(flat)
        )
        next_chapter_page = (
            flat[chapter_indices[unit_index + 1]][1]
            if unit_index + 1 < len(chapter_indices)
            else page_count
        )
        unit_end = max(chapter_start, next_chapter_page - 1)

        sections: list[OutlineSection] = []
        for entry_index in range(chapter_index + 1, next_chapter_index):
            section_title, section_start, section_end = flat[entry_index]
            if _is_chapter_marker(section_title):
                continue
            if entry_index + 1 < next_chapter_index:
                end = max(section_start, flat[entry_index + 1][1] - 1)
            else:
                end = max(section_start, unit_end)
            end = max(end, min(section_end, unit_end))
            sections.append(
                OutlineSection(title=section_title, page_start=section_start, page_end=end)
            )

        if not sections:
            sections.append(
                OutlineSection(
                    title=_clean_chapter_title(chapter_title),
                    page_start=chapter_start,
                    page_end=unit_end,
                )
            )

        units.append(
            OutlineUnit(
                id=str(len(units) + 1),
                title=_clean_chapter_title(chapter_title),
                page_start=chapter_start,
                page_end=unit_end,
                sections=sections,
            )
        )
    return units


def _normalize_hierarchical_toc(
    outline: DocumentOutline,
    parsed: list[tuple[int, str, int]],
    page_count: int,
) -> DocumentOutline | None:
    page_ends = _compute_page_ends(parsed, page_count)
    level_one = [(index, level, title, page_start) for index, (level, title, page_start) in enumerate(parsed) if level == 1]
    has_deeper = any(level >= 2 for level, _, _ in parsed)
    chapter_level_one = sum(1 for _, _, title, _ in level_one if _is_chapter_marker(title))

    if 3 <= chapter_level_one <= 12 and has_deeper:
        units: list[OutlineUnit] = []
        current_unit: OutlineUnit | None = None
        unit_counter = 0
        for index, (level, title, page_start) in enumerate(parsed):
            page_end = page_ends[index]
            if level == 1 and _is_chapter_marker(title):
                unit_counter += 1
                current_unit = OutlineUnit(
                    id=str(unit_counter),
                    title=_clean_chapter_title(title),
                    page_start=page_start,
                    page_end=page_end,
                    sections=[],
                )
                units.append(current_unit)
            elif level >= 2 and current_unit is not None:
                current_unit.sections.append(
                    OutlineSection(title=title, page_start=page_start, page_end=page_end)
                )
                current_unit.page_end = max(current_unit.page_end, page_end)
        if units:
            _finalize_unit_ranges(units)
            return _clone_outline_with_units(outline, units)

    if len(level_one) > 10 and has_deeper and chapter_level_one < 3:
        flat = [(title, page_start, page_ends[index]) for index, (_, title, page_start) in enumerate(parsed)]
        chapter_indices = [index for index, (title, _, _) in enumerate(flat) if _is_chapter_marker(title)]
        if len(chapter_indices) >= 3:
            units = _rollup_flat_by_chapters(flat, page_count, chapter_indices)
            if units:
                _finalize_unit_ranges(units)
                return _clone_outline_with_units(outline, units)

    return None


def normalize_outline_chapters(
    outline: DocumentOutline,
    *,
    toc_entries: list[tuple[int, str, int]] | None = None,
) -> tuple[DocumentOutline | None, OutlineGranularity | None]:
    """
    Roll up granular PDF TOC entries into PPL-like chapter units with nested sections.
    Returns (normalized outline, granularity) or (None, None) if too granular without chapters.
    """
    if toc_entries:
        hierarchical = _normalize_hierarchical_toc(outline, toc_entries, outline.page_count)
        if hierarchical is not None and not _too_granular_without_chapters(hierarchical):
            return hierarchical, "chapter"

    flat = _flatten_outline_entries(outline)
    chapter_indices = [index for index, (title, _, _) in enumerate(flat) if _is_chapter_marker(title)]

    if len(chapter_indices) >= 3 and (len(flat) >= 20 or len(flat) == len(chapter_indices)):
        units = _rollup_flat_by_chapters(flat, outline.page_count, chapter_indices)
        if units:
            normalized = _clone_outline_with_units(outline, units)
            _finalize_unit_ranges(normalized.units)
            if not _too_granular_without_chapters(normalized):
                return normalized, "chapter"
            return None, None

    if len(flat) >= 6 and len(chapter_indices) >= 3:
        units = _rollup_flat_by_chapters(flat, outline.page_count, chapter_indices)
        if units and len(units) >= 3:
            normalized = _clone_outline_with_units(outline, units)
            _finalize_unit_ranges(normalized.units)
            if not _too_granular_without_chapters(normalized):
                return normalized, "chapter"

    if 3 <= len(outline.units) <= 12:
        chapter_units = sum(1 for unit in outline.units if _is_chapter_marker(unit.title))
        if chapter_units >= 3:
            cleaned_units = [
                OutlineUnit(
                    id=unit.id,
                    title=_clean_chapter_title(unit.title) if _is_chapter_marker(unit.title) else unit.title,
                    page_start=unit.page_start,
                    page_end=unit.page_end,
                    sections=list(unit.sections),
                )
                for unit in outline.units
            ]
            normalized = _clone_outline_with_units(outline, cleaned_units)
            return normalized, "chapter"

    if _too_granular_without_chapters(outline):
        return None, None

    return outline, "section"


def _build_raw_outline_from_parsed(
    parsed: list[tuple[int, str, int]],
    *,
    page_count: int,
    document: str,
) -> DocumentOutline:
    page_ends = _compute_page_ends(parsed, page_count)
    units: list[OutlineUnit] = []
    current_unit: OutlineUnit | None = None
    unit_counter = 0
    has_level_one = any(level == 1 for level, _, _ in parsed)

    if has_level_one:
        for index, (level, title, page_start) in enumerate(parsed):
            page_end = page_ends[index]
            if level == 1:
                unit_counter += 1
                current_unit = OutlineUnit(
                    id=str(unit_counter),
                    title=title,
                    page_start=page_start,
                    page_end=page_end,
                    sections=[],
                )
                units.append(current_unit)
            elif current_unit is not None:
                current_unit.sections.append(
                    OutlineSection(title=title, page_start=page_start, page_end=page_end)
                )
                current_unit.page_end = max(current_unit.page_end, page_end)
    else:
        sections = [
            OutlineSection(title=title, page_start=page_start, page_end=page_ends[index])
            for index, (_level, title, page_start) in enumerate(parsed)
        ]
        units.append(
            OutlineUnit(
                id="1",
                title="Contents",
                page_start=sections[0].page_start,
                page_end=sections[-1].page_end,
                sections=sections,
            )
        )

    _finalize_unit_ranges(units)
    return DocumentOutline(
        document=document,
        course="",
        page_index_base=0,
        page_count=page_count,
        units=units,
    )


def _raw_outline_from_bookmarks(path: Path) -> tuple[DocumentOutline | None, list[tuple[int, str, int]] | None]:
    doc = fitz.open(path)
    try:
        raw_toc = doc.get_toc(simple=True)
        page_count = len(doc)
        if not raw_toc or page_count <= 0:
            return None, None

        parsed: list[tuple[int, str, int]] = []
        for level, title, page in raw_toc:
            clean_title = str(title).strip()
            if not clean_title:
                continue
            page_start = max(0, int(page) - 1)
            parsed.append((int(level), clean_title, page_start))

        if len(parsed) < 2:
            return None, None

        outline = _build_raw_outline_from_parsed(
            parsed,
            page_count=page_count,
            document=path.name,
        )
        return outline, parsed
    finally:
        doc.close()


def _parse_syllabus_unit_line(line: str) -> tuple[int, str, int] | None:
    """Parse a printed syllabus unit row: Unit N … page or N. Title … page."""
    clean = line.strip()
    if not clean:
        return None
    unit_match = _SYLLABUS_UNIT_LINE_RE.match(clean)
    if unit_match:
        unit_num = int(unit_match.group(1))
        title = f"Unit {unit_num} {unit_match.group(2).strip(' .')}".strip()
        page_number = int(unit_match.group(3))
        if unit_num > 0 and page_number > 0:
            return unit_num, title, page_number - 1
    numbered = _SYLLABUS_NUMBERED_UNIT_LINE_RE.match(clean)
    if numbered:
        unit_num = int(numbered.group(1))
        title = f"{unit_num}. {numbered.group(2).strip(' .')}".strip()
        page_number = int(numbered.group(3))
        if unit_num > 0 and page_number > 0:
            return unit_num, title, page_number - 1
    return None


def _parse_syllabus_units_from_pages(
    pages: list[PageText],
    *,
    max_pages: int = _TEXT_TOC_MAX_PAGES,
) -> list[tuple[str, int, int]] | None:
    """
    Parse early pages for a printed syllabus TOC (Units 1–N with page numbers).
    Returns (title, page_start, page_end) spans in 0-based page indices.
    """
    entries: list[tuple[int, str, int]] = []

    for page in _syllabus_toc_pages(pages, max_pages=max_pages):
        for line in page.text.splitlines():
            parsed = _parse_syllabus_unit_line(line)
            if parsed is not None:
                entries.append(parsed)

    if len(entries) < 3:
        return None

    entries.sort(key=lambda item: (item[0], item[2]))
    unit_numbers = [unit_num for unit_num, _, _ in entries]
    if unit_numbers[0] != 1:
        return None
    for index in range(1, len(unit_numbers)):
        if unit_numbers[index] != unit_numbers[index - 1] + 1:
            return None

    page_count = max(page.page for page in pages) if pages else 0
    page_count = max(page_count, entries[-1][2] + 1)
    spans: list[tuple[str, int, int]] = []
    for index, (_unit_num, title, page_start) in enumerate(entries):
        if index + 1 < len(entries):
            page_end = max(page_start, entries[index + 1][2] - 1)
        else:
            page_end = max(page_start, page_count - 1)
        spans.append((title, page_start, page_end))
    return spans


def _strip_syllabus_line_page_suffix(line: str) -> str:
    """Remove trailing '.... 12' page number so unit/subsection labels still parse."""
    return _SYLLABUS_TOC_PAGE_SUFFIX_RE.sub("", line).strip()


def _parse_syllabus_units_no_page_numbers(
    pages: list[PageText],
    *,
    max_pages: int = _TEXT_TOC_MAX_PAGES,
) -> list[tuple[int, str, list[str]]] | None:
    """
    Parse CONTENTS-style syllabus without trailing page numbers.
    Returns (major_unit_num, unit_title, subsection_titles) per major unit.
    """
    units: list[tuple[int, str, list[str]]] = []

    def _append_subsection(major: int, subsection_title: str) -> None:
        for index, (unit_major, unit_title, subs) in enumerate(units):
            if unit_major == major:
                units[index] = (unit_major, unit_title, subs + [subsection_title])
                return
        if units:
            last_major, last_title, subs = units[-1]
            units[-1] = (last_major, last_title, subs + [subsection_title])

    for page in _syllabus_toc_pages(pages, max_pages=max_pages):
        for line in page.text.splitlines():
            clean = _strip_syllabus_line_page_suffix(line.strip())
            if not clean:
                continue
            major_match = _SYLLABUS_MAJOR_UNIT_NO_PAGE_RE.match(clean)
            if major_match:
                major = int(major_match.group(1))
                rest = major_match.group(2).strip(" .")
                title = f"Unit {major} {rest}".strip() if rest else f"Unit {major}"
                units.append((major, title, []))
                continue
            parsed_sub = _parse_subsection_heading_line(clean)
            if parsed_sub:
                sub_major, _minor, label = parsed_sub
                _append_subsection(sub_major, label)

    if len(units) < 2:
        return None

    unit_numbers = [major for major, _, _ in units]
    if unit_numbers[0] != 1:
        return None
    for index in range(1, len(unit_numbers)):
        if unit_numbers[index] <= unit_numbers[index - 1]:
            return None
    return units


def _looks_like_subsection_title(title: str) -> bool:
    """Reject math fragments and numeric noise masquerading as headings."""
    clean = title.strip()
    if len(clean) < 3 or len(clean) > 120:
        return False
    if _MATHY_SUBSECTION_RE.search(clean):
        return False
    if _FORMULA_CONSTANT_RE.match(clean):
        return False
    if sum(char.isdigit() for char in clean) > len(clean) * 0.35:
        return False
    if sum(char.isalpha() for char in clean) < 3:
        return False
    return True


def _parse_subsection_heading_line(line: str) -> tuple[int, int, str] | None:
    """
    Parse '1.1 ELECTROCHEMISTRY' or 'UNIT 2.4 SURFACE ...' — not decimals like 2.303.
    Returns (major, minor, full_label).
    """
    clean = line.strip()
    if not clean:
        return None
    subunit = _SUBUNIT_HEADING_RE.match(clean)
    if subunit:
        major = int(subunit.group(1))
        minor = int(subunit.group(2))
        rest = clean[subunit.end() :].strip()
        if 1 <= minor <= _MAX_SUBSECTION_MINOR and _looks_like_subsection_title(rest or clean):
            return major, minor, clean
        return None
    numbered = _SUBSECTION_NUMERIC_TITLE_RE.match(clean)
    if numbered:
        major = int(numbered.group(1))
        minor = int(numbered.group(2))
        title = numbered.group(3).strip()
        if 1 <= minor <= _MAX_SUBSECTION_MINOR and _looks_like_subsection_title(title):
            return major, minor, f"{major}.{minor} {title}"
    return None


def _subsection_line_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        if _parse_subsection_heading_line(line.strip()) is not None:
            count += 1
    return count


def _is_likely_contents_page(page: PageText) -> bool:
    """Skip TOC/listing pages so 1.1 lines on CONTENTS are not treated as body anchors."""
    if not page.text.strip():
        return True
    if _TOC_HEADING_RE.search(page.text):
        return True
    if page.page <= 5 and _subsection_line_count(page.text) >= 4:
        return True
    return False


def _syllabus_toc_pages(pages: list[PageText], *, max_pages: int = _TEXT_TOC_MAX_PAGES) -> list[PageText]:
    """Front-matter pages that contain the printed syllabus / CONTENTS block."""
    toc_pages: list[PageText] = []
    for page in pages[:max_pages]:
        if _is_likely_contents_page(page) or (
            page.page <= 5 and _TOC_HEADING_RE.search(page.text)
        ):
            toc_pages.append(page)
        elif toc_pages:
            break
    return toc_pages


def _scan_body_subunit_details(
    pages: list[PageText],
) -> list[tuple[int, int, str, int]]:
    """Body hits for UNIT X.Y / X.Y headings: (major, minor, title, 0-based page index)."""
    details: list[tuple[int, int, str, int]] = []
    seen: set[tuple[int, int]] = set()

    def _record(major: int, minor: int, title: str, page_index: int) -> None:
        key = (major, minor, title.strip().lower())
        if key in seen:
            return
        seen.add(key)
        details.append((major, minor, title, page_index))

    for page in pages:
        if page.page <= 2 or _is_likely_contents_page(page):
            continue
        page_index = _page_index_from_page_text(page)
        for line in page.text.splitlines():
            parsed = _parse_subsection_heading_line(line.strip())
            if parsed is not None:
                major, minor, label = parsed
                _record(major, minor, label, page_index)
        for match in _SUBUNIT_IN_TEXT_RE.finditer(page.text):
            major = int(match.group(1))
            minor = int(match.group(2))
            label = f"UNIT {major}.{minor}"
            if _looks_like_subsection_title(label):
                _record(major, minor, label, page_index)

    details.sort(key=lambda item: (item[3], item[0], item[1]))
    return details


def _scan_major_unit_body_headings(pages: list[PageText]) -> dict[int, int]:
    """Major UNIT N headings in body (not UNIT N.M subunits)."""
    headings: dict[int, int] = {}
    for page in pages:
        if page.page <= 2 or _is_likely_contents_page(page):
            continue
        page_index = _page_index_from_page_text(page)
        for line in page.text.splitlines():
            match = _MAJOR_UNIT_BODY_LINE_RE.match(line.strip())
            if match:
                major = int(match.group(1))
                if major not in headings or page_index < headings[major]:
                    headings[major] = page_index
    return headings


def _detect_active_major_units(
    parsed_units: list[tuple[int, str, list[str]]],
    pages: list[PageText],
    subunit_details: list[tuple[int, int, str, int]],
) -> list[int]:
    """
    Choose real major units when CONTENTS lists more than the body supports.
    Prefers explicit UNIT N body headings; falls back to syllabus + X.1 anchors.
    """
    syllabus_majors = [major for major, _, _ in parsed_units]
    major_headings = _scan_major_unit_body_headings(pages)
    if len(major_headings) >= 2:
        return sorted(major_headings.keys())

    body_majors = sorted({major for major, _, _, _ in subunit_details})
    if not syllabus_majors:
        return body_majors

    unit_line_majors = [
        major
        for major in syllabus_majors
        if major in major_headings
    ]
    if len(unit_line_majors) >= 2:
        return unit_line_majors

    active: list[int] = []
    for major in syllabus_majors:
        has_first_sub = any(m == major and minor == 1 for m, minor, _, _ in subunit_details)
        has_any_sub = any(m == major for m, _, _, _ in subunit_details)
        if has_first_sub:
            active.append(major)
        elif has_any_sub and major == syllabus_majors[-1]:
            active.append(major)

    if len(active) >= 2:
        return active
    return syllabus_majors if len(syllabus_majors) >= 2 else body_majors


def _filter_parsed_units_to_majors(
    parsed_units: list[tuple[int, str, list[str]]],
    active_majors: list[int],
) -> list[tuple[int, str, list[str]]]:
    active_set = set(active_majors)
    return [entry for entry in parsed_units if entry[0] in active_set]


def _reassign_subunits_to_active_majors(
    details: list[tuple[int, int, str, int]],
    active_majors: list[int],
) -> list[tuple[int, int, str, int]]:
    """Orphan subunits (e.g. 3.1 between unit 2 and 5) roll into prior active major."""
    active = sorted(active_majors)
    if not active:
        return details
    active_set = set(active)
    major_anchor: dict[int, int] = {}
    for major, _minor, _title, page_index in details:
        if major in active_set:
            major_anchor[major] = min(major_anchor.get(major, page_index), page_index)

    reassigned: list[tuple[int, int, str, int]] = []
    for major, minor, label, page_index in details:
        if major in active_set:
            reassigned.append((major, minor, label, page_index))
            continue
        owner_candidates = [candidate for candidate in active if major_anchor.get(candidate, 0) <= page_index]
        owner = max(owner_candidates) if owner_candidates else active[0]
        reassigned.append((owner, minor, label, page_index))
    return reassigned


def _subsection_label_parts(label: str) -> tuple[int, int] | None:
    parsed = _parse_subsection_heading_line(label)
    if parsed:
        return parsed[0], parsed[1]
    match = _SYLLABUS_SUBSECTION_TITLE_PARTS_RE.match(label.strip())
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def _sections_for_major_unit(
    major: int,
    unit_start: int,
    unit_end: int,
    subunit_details: list[tuple[int, int, str, int]],
    contents_subsections: list[str],
) -> list[OutlineSection]:
    """Sections from body subunit anchors; CONTENTS labels fill gaps; no bookmark noise."""
    contents_labels: dict[int, list[str]] = {}
    for subsection in contents_subsections:
        parts = _subsection_label_parts(subsection)
        if parts and parts[0] == major:
            contents_labels.setdefault(parts[1], []).append(subsection.strip())

    by_key: dict[tuple[int, str], tuple[str, int]] = {}
    for hit_major, minor, label, page_index in subunit_details:
        if hit_major != major:
            continue
        page_index = max(unit_start, min(page_index, unit_end))
        display = label
        for candidate in contents_labels.get(minor, []):
            if candidate.lower().startswith(f"{major}.{minor}"):
                display = candidate
                break
        key = (minor, display.strip().lower())
        if key not in by_key or page_index < by_key[key][1]:
            by_key[key] = (display, page_index)

    for minor, labels in contents_labels.items():
        for label in labels:
            key = (minor, label.strip().lower())
            if key not in by_key:
                by_key[key] = (label, unit_start)

    if not by_key:
        return []

    ordered = sorted(by_key.values(), key=lambda item: (item[1], item[0]))
    sections: list[OutlineSection] = []
    for index, (label, page_start) in enumerate(ordered):
        page_start = max(unit_start, min(page_start, unit_end))
        if index + 1 < len(ordered):
            page_end = max(page_start, ordered[index + 1][1] - 1)
        else:
            page_end = unit_end
        page_end = max(page_start, min(page_end, unit_end))
        sections.append(OutlineSection(title=label, page_start=page_start, page_end=page_end))
    return sections


def _scan_body_subunit_anchors(pages: list[PageText]) -> dict[int, int]:
    """Earliest body page per major unit (min of UNIT X.Y / X.Y hits, excluding CONTENTS pages)."""
    anchors: dict[int, int] = {}
    for major, _minor, _title, page_index in _scan_body_subunit_details(pages):
        if major not in anchors or page_index < anchors[major]:
            anchors[major] = page_index
    return anchors


def _subunit_page_map(details: list[tuple[int, int, str, int]]) -> dict[tuple[int, int], int]:
    pages: dict[tuple[int, int], int] = {}
    for major, minor, _title, page_index in details:
        key = (major, minor)
        if key not in pages or page_index < pages[key]:
            pages[key] = page_index
    return pages


def _fill_major_start_pages(
    majors_sorted: list[int],
    major_starts: dict[int, int],
    *,
    default_after_toc: int = 3,
    page_count: int,
) -> dict[int, int]:
    """Interpolate missing major-unit start pages between known body anchors."""
    filled = dict(major_starts)
    if not majors_sorted:
        return filled

    if majors_sorted[0] not in filled:
        filled[majors_sorted[0]] = default_after_toc

    known_positions = [index for index, major in enumerate(majors_sorted) if major in filled]
    if not known_positions:
        step = max(1, (page_count - default_after_toc) // max(len(majors_sorted), 1))
        for index, major in enumerate(majors_sorted):
            filled[major] = min(page_count - 1, default_after_toc + index * step)
        return filled

    for slot in range(len(known_positions) - 1):
        left_index = known_positions[slot]
        right_index = known_positions[slot + 1]
        left_major = majors_sorted[left_index]
        right_major = majors_sorted[right_index]
        left_page = filled[left_major]
        right_page = filled[right_major]
        gap = right_index - left_index
        for offset in range(1, gap):
            major = majors_sorted[left_index + offset]
            if major not in filled:
                filled[major] = int(left_page + (offset / gap) * (right_page - left_page))

    # Fill majors before the first known anchor.
    first_index = known_positions[0]
    if first_index > 0:
        anchor_major = majors_sorted[first_index]
        anchor_page = filled[anchor_major]
        for offset in range(first_index, 0, -1):
            major = majors_sorted[offset - 1]
            if major not in filled:
                filled[major] = max(0, anchor_page - (first_index - offset + 1))

    last_index = known_positions[-1]
    if last_index < len(majors_sorted) - 1:
        anchor_major = majors_sorted[last_index]
        anchor_page = filled[anchor_major]
        for offset in range(last_index + 1, len(majors_sorted)):
            major = majors_sorted[offset]
            if major not in filled:
                filled[major] = min(page_count - 1, anchor_page + (offset - last_index))

    for index in range(1, len(majors_sorted)):
        major = majors_sorted[index]
        previous = majors_sorted[index - 1]
        if major in filled and previous in filled:
            filled[major] = max(filled[major], filled[previous] + 1)

    return filled


def _normalize_monotonic_unit_spans(
    spans: list[tuple[str, int, int]],
    page_count: int,
) -> list[tuple[str, int, int]]:
    """Force unit page ranges to be non-overlapping and in unit order."""
    if len(spans) < 2:
        return spans

    starts: list[int] = []
    for _title, page_start, _page_end in spans:
        if starts:
            page_start = max(page_start, starts[-1] + 1)
        starts.append(page_start)

    normalized: list[tuple[str, int, int]] = []
    last_page = max(page_count, 1) - 1
    for index, (title, _old_start, _old_end) in enumerate(spans):
        page_start = starts[index]
        if index + 1 < len(starts):
            page_end = max(page_start, starts[index + 1] - 1)
        else:
            page_end = max(page_start, last_page)
        normalized.append((title, page_start, page_end))
    return normalized


def _syllabus_page_spans_look_spurious(spans: list[tuple[str, int, int]]) -> bool:
    """True when dotted TOC page numbers cluster on the same front-matter page."""
    if len(spans) < 3:
        return False
    starts = [page_start for _, page_start, _ in spans]
    if len(set(starts)) == 1 and starts[0] <= 4:
        return True
    early = [page_start for page_start in starts if page_start <= 4]
    if len(early) >= len(starts) - 1 and len(set(early)) == 1:
        return True
    # One outlier page number (e.g. unit 3 at p.14) while most units share p.3.
    if early:
        most_common_start, count = Counter(early).most_common(1)[0]
        if count >= 3 and count >= len(starts) * 0.6:
            return True
    return False


def _build_syllabus_spans_from_no_page_toc(
    parsed_units: list[tuple[int, str, list[str]]],
    pages: list[PageText],
    page_count: int,
    *,
    subunit_details: list[tuple[int, int, str, int]] | None = None,
) -> list[tuple[str, int, int]] | None:
    """Build (title, page_start, page_end) spans from syllabus labels and body anchors."""
    if len(parsed_units) < 2:
        return None

    majors_sorted = [major for major, _, _ in sorted(parsed_units, key=lambda item: item[0])]
    if subunit_details:
        anchor_source: dict[int, int] = {}
        for major, _minor, _title, page_index in subunit_details:
            if major not in anchor_source or page_index < anchor_source[major]:
                anchor_source[major] = page_index
    else:
        anchor_source = _scan_body_subunit_anchors(pages)
    major_starts = _fill_major_start_pages(
        majors_sorted,
        anchor_source,
        page_count=page_count,
    )
    zero_based_page_count = max(page_count, 1)
    unit_by_major = {major: (title, subs) for major, title, subs in parsed_units}

    spans: list[tuple[str, int, int]] = []
    for index, major in enumerate(majors_sorted):
        title, _subsections = unit_by_major[major]
        page_start = major_starts[major]
        if index + 1 < len(majors_sorted):
            next_major = majors_sorted[index + 1]
            page_end = max(page_start, major_starts[next_major] - 1)
        else:
            page_end = max(page_start, zero_based_page_count - 1)
        spans.append((title, page_start, page_end))

    if len(spans) < 2:
        return None
    return _normalize_monotonic_unit_spans(spans, zero_based_page_count)


def _sections_from_syllabus_subsections(
    major: int,
    subsections: list[str],
    subunit_pages: dict[tuple[int, int], int],
    unit_start: int,
    unit_end: int,
) -> list[OutlineSection]:
    """Build nested sections from CONTENTS subsection labels and body subunit anchors."""
    if not subsections:
        return []

    parsed_subs: list[tuple[int, int, str, int]] = []
    for subsection_title in subsections:
        match = _SYLLABUS_SUBSECTION_TITLE_PARTS_RE.match(subsection_title.strip())
        if match:
            sub_major = int(match.group(1))
            minor = int(match.group(2))
            label = subsection_title.strip()
            page_start = subunit_pages.get((sub_major, minor), unit_start)
            parsed_subs.append((sub_major, minor, label, page_start))
        else:
            parsed_subs.append((major, len(parsed_subs) + 1, subsection_title.strip(), unit_start))

    parsed_subs.sort(key=lambda item: (item[3], item[1]))
    clipped: list[tuple[int, int, str, int]] = []
    for sub_major, minor, label, page_start in parsed_subs:
        page_start = max(unit_start, min(page_start, unit_end))
        if clipped and page_start < clipped[-1][3]:
            page_start = clipped[-1][3]
        clipped.append((sub_major, minor, label, page_start))

    sections: list[OutlineSection] = []
    for index, (_sub_major, _minor, label, page_start) in enumerate(clipped):
        if index + 1 < len(clipped):
            page_end = max(page_start, clipped[index + 1][3] - 1)
        else:
            page_end = unit_end
        page_end = max(page_start, min(page_end, unit_end))
        sections.append(
            OutlineSection(title=label, page_start=page_start, page_end=page_end),
        )
    return sections


def _syllabus_unit_index_for_major(
    major: int,
    syllabus_units: list[tuple[str, int, int]],
) -> int | None:
    for index, (title, _, _) in enumerate(syllabus_units):
        title_major = _major_unit_from_title(title)
        if title_major == major:
            return index
    if 1 <= major <= len(syllabus_units):
        return major - 1
    return None


def _syllabus_unit_index_for_page(
    page_start: int,
    syllabus_units: list[tuple[str, int, int]],
) -> int:
    for index, (_title, unit_start, unit_end) in enumerate(syllabus_units):
        if unit_start <= page_start <= unit_end:
            return index
    before = [index for index, (_, start, _) in enumerate(syllabus_units) if start <= page_start]
    if before:
        return before[-1]
    return 0


def _merge_outline_to_syllabus_units(
    outline: DocumentOutline,
    syllabus_units: list[tuple[str, int, int]],
    *,
    syllabus_parsed: list[tuple[int, str, list[str]]] | None = None,
    subunit_pages: dict[tuple[int, int], int] | None = None,
    subunit_details: list[tuple[int, int, str, int]] | None = None,
    prefer_syllabus_subsections: bool = False,
) -> DocumentOutline | None:
    """Map bookmark/heading sections into printed syllabus unit page spans."""
    flat = _flatten_outline_entries(outline)
    if not syllabus_units or len(syllabus_units) < 2:
        return None

    bucketed: list[list[OutlineSection]] = [[] for _ in syllabus_units]
    if flat and not prefer_syllabus_subsections:
        for title, page_start, page_end in flat:
            if _is_chapter_marker(title) and len(flat) > len(syllabus_units) * 2:
                continue
            if _MATHY_SUBSECTION_RE.search(title) or _parse_subsection_heading_line(title) is None and re.match(
                r"^\d+\.\d",
                title.strip(),
            ):
                if not _looks_like_subsection_title(title):
                    continue
            unit_index = _syllabus_unit_index_for_page(page_start, syllabus_units)
            major = _major_unit_from_title(title)
            if major is not None:
                major_index = _syllabus_unit_index_for_major(major, syllabus_units)
                if major_index is not None:
                    unit_index = major_index
            _unit_title, unit_start, unit_end = syllabus_units[unit_index]
            clipped_start = max(page_start, unit_start)
            clipped_end = min(page_end, unit_end)
            if clipped_start > clipped_end:
                continue
            bucketed[unit_index].append(
                OutlineSection(title=title, page_start=clipped_start, page_end=clipped_end)
            )

    parsed_by_major: dict[int, tuple[str, list[str]]] = {}
    if syllabus_parsed:
        parsed_by_major = {major: (title, subs) for major, title, subs in syllabus_parsed}

    units: list[OutlineUnit] = []
    for index, (title, unit_start, unit_end) in enumerate(syllabus_units):
        sections = bucketed[index]
        major = _major_unit_from_title(title) or (index + 1)
        parsed_title, parsed_subsections = parsed_by_major.get(major, (title, []))
        if parsed_title and parsed_title.lower().startswith("unit "):
            title = parsed_title
        placeholder_only = (
            len(sections) == 1
            and sections[0].title.strip().lower() == title.strip().lower()
        )
        has_subunit_sections = any(
            _SYLLABUS_SUBSECTION_TITLE_PARTS_RE.match(section.title.strip())
            for section in sections
        )
        if (
            prefer_syllabus_subsections
            and subunit_details is not None
        ):
            sections = _sections_for_major_unit(
                major,
                unit_start,
                unit_end,
                subunit_details,
                parsed_subsections,
            )
        elif (
            parsed_subsections
            and subunit_pages is not None
            and (
                prefer_syllabus_subsections
                or not sections
                or placeholder_only
                or not has_subunit_sections
            )
        ):
            sections = _sections_from_syllabus_subsections(
                major,
                parsed_subsections,
                subunit_pages,
                unit_start,
                unit_end,
            )
        if not sections:
            sections = [
                OutlineSection(title=title, page_start=unit_start, page_end=unit_end),
            ]
        units.append(
            OutlineUnit(
                id=str(index + 1),
                title=title,
                page_start=unit_start,
                page_end=unit_end,
                sections=sections,
            )
        )

    _finalize_unit_ranges(units)
    return _clone_outline_with_units(outline, units)


def _merge_units_to_target_count(units: list[OutlineUnit], target: int) -> list[OutlineUnit]:
    merged = _clone_units(units)
    while len(merged) > target:
        if not _merge_smallest_unit(merged):
            break
    return merged


def _apply_syllabus_unit_merge(
    outline: DocumentOutline,
    pages: list[PageText] | None,
) -> tuple[DocumentOutline, OutlineGranularity | None] | None:
    """
    When a printed syllabus TOC defines N units, merge extracted outline to N units.
    Falls back to merging adjacent units when section count suggests syllabus-style rollup.
    """
    syllabus_units = _parse_syllabus_units_from_pages(pages) if pages else None
    spurious_page_spans = bool(syllabus_units and _syllabus_page_spans_look_spurious(syllabus_units))
    if spurious_page_spans:
        syllabus_units = None

    no_page_units = (
        _parse_syllabus_units_no_page_numbers(pages) if pages else None
    )
    subunit_details = _scan_body_subunit_details(pages) if pages else []
    body_anchor_count = len(_scan_body_subunit_anchors(pages)) if pages else 0
    prefer_no_page_merge = bool(
        no_page_units
        and len(no_page_units) >= 2
        and (spurious_page_spans or body_anchor_count >= 2)
    )

    if prefer_no_page_merge and pages and no_page_units:
        active_majors = _detect_active_major_units(no_page_units, pages, subunit_details)
        filtered_units = _filter_parsed_units_to_majors(no_page_units, active_majors)
        reassigned_details = _reassign_subunits_to_active_majors(subunit_details, active_majors)
        subunit_pages = _subunit_page_map(reassigned_details)
        page_count = max((page.page for page in pages), default=1)
        no_page_spans = _build_syllabus_spans_from_no_page_toc(
            filtered_units,
            pages,
            page_count,
            subunit_details=reassigned_details,
        )
        if no_page_spans:
            merged = _merge_outline_to_syllabus_units(
                outline,
                no_page_spans,
                syllabus_parsed=filtered_units,
                subunit_pages=subunit_pages,
                subunit_details=reassigned_details,
                prefer_syllabus_subsections=True,
            )
            if merged is not None and validate_extracted_outline(merged):
                return merged, "chapter"

    if syllabus_units:
        merged = _merge_outline_to_syllabus_units(outline, syllabus_units)
        if merged is not None and validate_extracted_outline(merged):
            return merged, "chapter"

    target = len(syllabus_units) if syllabus_units else None
    if target is None and 6 <= len(outline.units) <= _MAX_UNITS_CAP:
        if _section_count(outline) >= 15 and not _too_granular_without_chapters(outline):
            target = 5

    if target is not None and len(outline.units) > target:
        merged_units = _merge_units_to_target_count(outline.units, target)
        if len(merged_units) == target:
            merged = _clone_outline_with_units(outline, merged_units)
            _finalize_unit_ranges(merged.units)
            if validate_extracted_outline(merged):
                return merged, "chapter"
    return None


def _parse_text_toc_line(line: str) -> tuple[str, int] | None:
    clean = line.strip()
    if not clean or len(clean) < 4:
        return None
    chapter_with_dots = re.match(
        r"^((?:chapter|unit|module|part)\s+(?:[0-9]+|[IVXLCDM]+)\s+.+?)\s+\.{2,}\s*(\d+)\s*$",
        clean,
        re.I,
    )
    if chapter_with_dots:
        title = chapter_with_dots.group(1).strip(" .")
        page_number = int(chapter_with_dots.group(2))
        if title and page_number > 0:
            return title, page_number - 1
    for pattern in (_TOC_CHAPTER_LINE_RE, _TOC_DOTS_LINE_RE):
        match = pattern.match(clean)
        if match:
            title = match.group(1).strip(" .")
            page_number = int(match.group(2))
            if title and page_number > 0:
                return title, page_number - 1
    return None


def _raw_outline_from_text_toc(
    pages: list[PageText],
    *,
    max_pages: int = _TEXT_TOC_MAX_PAGES,
) -> DocumentOutline | None:
    """Parse textual TOC without normalization."""
    toc_started = False
    entries: list[tuple[str, int]] = []

    for page in pages[:max_pages]:
        if not page.text.strip():
            continue
        if not toc_started:
            if _TOC_HEADING_RE.search(page.text):
                toc_started = True
            else:
                continue

        for line in page.text.splitlines():
            parsed = _parse_text_toc_line(line)
            if parsed is not None:
                entries.append(parsed)

    if len(entries) < 2:
        return None

    page_count = max(page.page for page in pages) if pages else 0
    sections: list[OutlineSection] = []
    for index, (title, page_start) in enumerate(entries):
        if index + 1 < len(entries):
            page_end = max(page_start, entries[index + 1][1] - 1)
        else:
            page_end = max(page_start, page_count - 1 if page_count > 0 else page_start)
        sections.append(OutlineSection(title=title, page_start=page_start, page_end=page_end))

    units = [
        OutlineUnit(
            id="1",
            title="Contents",
            page_start=sections[0].page_start,
            page_end=sections[-1].page_end,
            sections=sections,
        )
    ]
    outline = DocumentOutline(
        document="",
        course="",
        page_index_base=0,
        page_count=max(page_count, sections[-1].page_end + 1),
        units=units,
    )
    return outline


def _normalize_engineering_roman_token(token: str) -> str:
    """Repair common OCR mistakes in Roman unit index tokens."""
    clean = token.strip().upper().replace("L", "I")
    for ocr_error, repaired in (("IIL", "III"), ("IL", "II"), ("II1", "III")):
        if clean == ocr_error:
            return repaired
    return clean


def _parse_engineering_unit_index(token: str) -> int | None:
    clean = _normalize_engineering_roman_token(token)
    if clean.isdigit():
        value = int(clean)
        return value if value >= 1 else None
    return _ROMAN_NUMERAL_VALUES.get(clean)


def _match_engineering_unit_header(line: str) -> tuple[int | None, str] | None:
    return _match_engineering_syllabus_unit_header(line, allow_arabic=False)


def _match_engineering_syllabus_unit_header(
    line: str,
    *,
    allow_arabic: bool = True,
) -> tuple[int | None, str] | None:
    clean = line.strip()
    if not clean:
        return None

    patterns = [
        _ENGINEERING_UNIT_DASHED_RE,
        _ENGINEERING_UNIT_HYPHEN_DIGIT_RE,
        _ENGINEERING_UNIT_ROMAN_RE,
    ]
    if allow_arabic:
        patterns.append(_ENGINEERING_UNIT_ARABIC_RE)

    for pattern in patterns:
        match = pattern.match(clean)
        if match is None:
            continue
        index_token = match.group("index")
        if index_token.isdigit() and pattern is _ENGINEERING_UNIT_ROMAN_RE:
            continue
        unit_index = _parse_engineering_unit_index(index_token)
        rest = match.group("rest").strip(" -–:")
        rest = _SYLLABUS_TOC_PAGE_SUFFIX_RE.sub("", rest).strip()
        normalized_token = _normalize_engineering_roman_token(index_token)
        title = f"Unit {normalized_token} {rest}".strip() if rest else f"Unit {normalized_token}"
        return unit_index, title
    return None


def _match_engineering_structure_unit_header(line: str) -> tuple[int | None, str] | None:
    """Match UNIT headers for structure import, including plain Arabic ``Unit 1`` lines."""
    return _match_engineering_syllabus_unit_header(line, allow_arabic=True)


def _merge_wrapped_pdf_lines(lines: list[str]) -> list[str]:
    """Join broken PDF line wraps before syllabus parsing."""
    if not lines:
        return []

    merged: list[str] = []
    buffer = lines[0].strip()
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            if buffer:
                merged.append(buffer)
                buffer = ""
            continue
        if not buffer:
            buffer = stripped
            continue
        if _should_merge_wrapped_pdf_line(buffer, stripped):
            if buffer.endswith("-"):
                buffer = buffer[:-1] + stripped
            else:
                buffer = f"{buffer} {stripped}"
        else:
            merged.append(buffer)
            buffer = stripped
    if buffer:
        merged.append(buffer)
    return merged


def _is_orphan_syllabus_fragment_line(line: str) -> bool:
    return bool(re.match(r"^[a-z]{1,3},\s", line.strip()))


def _should_merge_wrapped_pdf_line(previous: str, nxt: str) -> bool:
    if _match_engineering_structure_unit_header(nxt) is not None:
        return False
    if _is_engineering_syllabus_part_heading_line(nxt):
        return False
    if _is_orphan_syllabus_fragment_line(nxt):
        return False
    if previous.rstrip().endswith(".") and _is_orphan_syllabus_fragment_line(nxt):
        return False
    if previous.count("(") > previous.count(")"):
        return True
    if previous.endswith(":"):
        return False
    if previous.endswith("-") and nxt and nxt[0].isalpha():
        return True
    if nxt and nxt[0].islower():
        last_token = previous.rsplit(None, 1)[-1] if previous.split() else ""
        if not re.search(r"[.:;!?)]$", previous.rstrip()):
            if (
                previous.endswith("-")
                or ("-" in last_token)
                or (last_token.isalpha() and len(last_token) >= 4)
            ):
                return True
    if previous.endswith(","):
        return True
    if previous.endswith(" and") or previous.endswith(" and."):
        return True
    trailing = previous.rsplit(None, 1)[-1].lower()
    if trailing in {"of", "and", "or", "the", "a", "an", "to", "in", "for", "with", "flow"}:
        return True
    if not re.search(r"[.:;!?)]$", previous.rstrip()):
        last_token_lower = previous.rsplit(None, 1)[-1].lower() if previous.split() else ""
        if (
            last_token_lower in {"multiple", "simple", "basic", "advanced", "general"}
            and nxt
            and nxt[0].isupper()
        ):
            return True
    if ":" in previous and nxt and nxt.split():
        first_word = re.sub(r"[^A-Za-z].*$", "", nxt.split()[0])
        prev_stripped = previous.rstrip()
        if (
            first_word
            and first_word[0].isupper()
            and first_word.isalpha()
            and (
                prev_stripped.endswith("-")
                or bool(re.search(r"\bK-Means$", prev_stripped, re.I))
            )
        ):
            return True
    if (
        "," in previous
        and not previous.rstrip().endswith(",")
        and nxt.split()
        and nxt.split()[0][0].isupper()
    ):
        return False
    if not re.search(r"[.:;!?)]$", previous) and len(nxt.split()) <= 6:
        return True
    return False


def _cleanup_syllabus_topic(title: str) -> str:
    return re.sub(r"\.\s+s$", "", title.strip()).strip()


def _looks_like_comma_separated_topic_list(text: str) -> bool:
    """True when text looks like a flat comma-separated syllabus topic list."""
    segments = [segment.strip() for segment in text.split(",") if segment.strip()]
    if len(segments) < 3:
        return False
    if any(segment.lower().startswith("and ") for segment in segments):
        return False
    short_segments = sum(
        1 for segment in segments if len(segment) <= 80 and segment.count(".") <= 1
    )
    return short_segments / len(segments) >= 0.7


def _flat_syllabus_topics(merged_lines: list[str]) -> list[str]:
    topics: list[str] = []
    for line in merged_lines:
        clean = line.strip()
        if not clean:
            continue
        if _looks_like_comma_separated_topic_list(clean):
            topics.extend(_split_comma_separated_topics(clean))
        else:
            topics.extend(_engineering_syllabus_topic_titles(clean))
    if topics:
        return topics
    joined = " ".join(merged_lines).strip()
    return _engineering_syllabus_topic_titles(joined)


def _should_split_topic_on_period(current: str, *, at_end: bool, next_char: str | None) -> bool:
    """Split syllabus inline lists on period boundaries (e.g. 'A. B. C'), not decimals."""
    topic = current.strip()
    if not topic or len(topic) < 3:
        return False
    if topic[-1].isdigit():
        return False
    if at_end:
        return True
    return next_char == " " if next_char is not None else False


def _split_comma_separated_topics(text: str) -> list[str]:
    """Split comma- or period-separated syllabus topics, ignoring delimiters inside parentheses."""
    clean = re.sub(r"\s+", " ", text.strip())
    if not clean:
        return []

    topics: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    while index < len(clean):
        char = clean[index]
        next_char = clean[index + 1] if index + 1 < len(clean) else None
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif depth == 0 and char == ",":
            topic = "".join(current).strip(" ,;.")
            if topic:
                topics.append(_cleanup_syllabus_topic(topic))
            current = []
        elif depth == 0 and char == "." and _should_split_topic_on_period(
            "".join(current),
            at_end=next_char is None,
            next_char=next_char,
        ):
            topic = "".join(current).strip(" ,;.")
            if topic:
                topics.append(_cleanup_syllabus_topic(topic))
            current = []
        else:
            current.append(char)
        index += 1
    topic = "".join(current).strip(" ,;.")
    if topic:
        topics.append(_cleanup_syllabus_topic(topic))
    return topics


def _is_engineering_inline_part_continuation(part_title: str) -> bool:
    """True for wrapped acronym continuations like ``DHCP.Network Routing Algorithms``."""
    clean = part_title.strip()
    return bool(re.match(r"^[A-Z]{2,}\.", clean))


def _looks_like_engineering_part_heading_prefix(prefix: str) -> bool:
    clean = prefix.strip()
    if not clean or len(clean) > 80:
        return False
    if _is_engineering_inline_part_continuation(clean):
        return False
    if _match_engineering_structure_unit_header(clean) is not None:
        return False
    if _ENGINEERING_FOOTER_READINGS_RE.match(clean):
        return False
    if _ENGINEERING_FOOTER_PROGRAM_RE.match(clean):
        return False
    if re.search(r"[(),]", clean):
        return False
    if len(clean.split()) > 12:
        return False
    return clean[0].isupper()


def _split_engineering_part_heading_line(line: str) -> tuple[str | None, str]:
    """Return (part_title, remainder) for standalone or inline part headings."""
    clean = line.strip()
    if not clean:
        return None, ""

    if clean.endswith(":") and clean.count(":") == 1:
        prefix = clean.rstrip(":").strip()
        if _looks_like_engineering_part_heading_prefix(prefix):
            return prefix, ""
        return None, clean

    colon_pos = clean.find(":")
    if colon_pos > 0:
        prefix = clean[:colon_pos].strip()
        suffix = clean[colon_pos + 1 :].strip()
        if _looks_like_engineering_part_heading_prefix(prefix):
            return prefix, suffix
    return None, clean


def _is_false_embedded_heading_after_acronym(text: str, match: re.Match[str]) -> bool:
    """Skip embedded headings immediately after an acronym period (e.g. ``DHCP.``)."""
    pos = match.start()
    while pos > 0 and text[pos - 1].isspace():
        pos -= 1
    if pos == 0 or text[pos - 1] != ".":
        return False
    pos -= 1
    acronym_len = 0
    while pos > 0 and text[pos - 1].isupper():
        acronym_len += 1
        pos -= 1
    return acronym_len >= 2


def _is_spurious_embedded_part_heading(prefix: str, remainder: str) -> bool:
    """Skip generic single-word headings with at most one short trailing topic."""
    title = prefix.strip()
    if len(title.split()) != 1:
        return False
    if title.lower() not in _SPURIOUS_EMBEDDED_PART_WORDS:
        return False
    short_topics = [topic for topic in _split_comma_separated_topics(remainder) if len(topic) <= 20]
    return len(short_topics) <= 1


def _find_valid_embedded_part_matches(
    line: str,
    *,
    allow_spurious_part_words: bool = False,
) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    search_from = 0
    while True:
        match = _ENGINEERING_EMBEDDED_PART_HEADING_RE.search(line, search_from)
        if match is None:
            break
        if _is_false_embedded_heading_after_acronym(line, match):
            search_from = match.end()
            continue
        embedded_title = match.group(1).strip()
        remainder = line[match.end() :].strip()
        spurious = _is_spurious_embedded_part_heading(embedded_title, remainder)
        if (
            "," in embedded_title
            or _is_engineering_inline_part_continuation(embedded_title)
            or not _looks_like_engineering_part_heading_prefix(embedded_title)
            or (spurious and not allow_spurious_part_words)
        ):
            search_from = match.end()
            continue
        matches.append(match)
        search_from = match.end()
    return matches


def _split_line_at_embedded_parts(
    line: str,
    matches: list[re.Match[str]],
) -> list[tuple[str | None, str]]:
    if not matches:
        return [(None, line.strip())]

    segments: list[tuple[str | None, str]] = []
    clean = line.strip()
    prefix = clean[: matches[0].start()].strip(" .,;")
    if prefix:
        comma_topics = _split_comma_separated_topics(prefix)
        if comma_topics:
            first_part_title = comma_topics[0]
            leading_topics = ", ".join(comma_topics[1:]) if len(comma_topics) > 1 else ""
            segments.append((first_part_title, leading_topics))

    for index, match in enumerate(matches):
        part_title = match.group(1).strip()
        if index + 1 < len(matches):
            topic_text = clean[match.end() : matches[index + 1].start()].strip(" .,;")
        else:
            topic_text = clean[match.end() :].strip(" .,;")
        segments.append((part_title, topic_text))

    return segments if segments else [(None, clean)]


def _iter_engineering_part_segments(line: str) -> list[tuple[str | None, str]]:
    """Split a syllabus line into ordered (part_title, topic_text) segments."""
    clean = line.strip()
    if not clean:
        return []

    first_title, first_remainder = _split_engineering_part_heading_line(clean)
    if first_title is None:
        matches = _find_valid_embedded_part_matches(clean)
        if matches:
            return _split_line_at_embedded_parts(clean, matches)
        return [(None, clean)]

    segments: list[tuple[str | None, str]] = []
    current_title = first_title
    topic_chunk = first_remainder
    matches = _find_valid_embedded_part_matches(
        topic_chunk,
        allow_spurious_part_words=True,
    )

    if not matches:
        trimmed = topic_chunk.strip(" .,;")
        if trimmed or not segments:
            segments.append((current_title, trimmed))
        return segments

    prefix = topic_chunk[: matches[0].start()].strip(" .,;")
    segments.append((current_title, prefix))
    for index, match in enumerate(matches):
        part_title = match.group(1).strip()
        if index + 1 < len(matches):
            topic_text = topic_chunk[match.end() : matches[index + 1].start()].strip(" .,;")
        else:
            topic_text = topic_chunk[match.end() :].strip(" .,;")
        segments.append((part_title, topic_text))

    return segments


def _merged_line_has_part_structure(line: str, *, is_bold: bool = False) -> bool:
    clean = line.strip()
    if not clean:
        return False
    if _is_engineering_syllabus_part_heading_line(clean, is_bold=is_bold):
        return True
    return bool(_find_valid_embedded_part_matches(clean))


def _is_engineering_syllabus_part_heading_line(line: str, *, is_bold: bool = False) -> bool:
    clean = line.strip()
    if not clean or _match_engineering_structure_unit_header(clean) is not None:
        return False
    part_title, _remainder = _split_engineering_part_heading_line(clean)
    if part_title is not None and clean.lower().startswith(part_title.lower()):
        return True
    if not is_bold:
        return False
    if "," in clean:
        return False
    return len(clean.split()) <= 12


def _strip_engineering_syllabus_footer_lines(
    body_lines: list[tuple[str, bool]],
) -> list[tuple[str, bool]]:
    """Drop bibliography footers and program page stamps before unit-body parsing."""
    filtered: list[tuple[str, bool]] = []
    for line, is_bold in body_lines:
        clean = line.strip()
        if not clean:
            continue
        if _ENGINEERING_FOOTER_READINGS_RE.match(clean):
            break
        if _ENGINEERING_FOOTER_PROGRAM_RE.match(clean):
            continue
        if re.search(r"page\s+\d+\s*$", clean, re.I) and _ENGINEERING_FOOTER_PROGRAM_RE.search(clean):
            continue
        filtered.append((line, is_bold))
    return filtered


def _iter_engineering_syllabus_lines(page: PageText) -> list[tuple[str, bool]]:
    page_dict = page.metadata.get("page_dict")
    if isinstance(page_dict, dict):
        styled: list[tuple[str, bool]] = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(str(span.get("text", "")) for span in spans).strip()
                if not text:
                    continue
                is_bold = any("bold" in str(span.get("font", "")).lower() for span in spans)
                styled.append((text, is_bold))
        if styled:
            return styled
    return [(line, False) for line in page.text.splitlines()]


def _parse_engineering_syllabus_unit_body(
    body_lines: list[tuple[str, bool]],
) -> tuple[list[EngineeringSyllabusPart] | None, list[str]]:
    body_lines = _strip_engineering_syllabus_footer_lines(body_lines)
    merged_lines = _merge_wrapped_pdf_lines([line for line, _bold in body_lines if line.strip()])
    merged_lines = [
        line for line in merged_lines if not _is_orphan_syllabus_fragment_line(line)
    ]
    if not merged_lines:
        return None, []

    bold_by_line = {line.strip(): bold for line, bold in body_lines if line.strip()}
    has_part_headings = any(
        _merged_line_has_part_structure(
            line.strip(),
            is_bold=bold_by_line.get(line.strip(), False),
        )
        for line in merged_lines
        if line.strip()
    )
    if not has_part_headings:
        return None, _flat_syllabus_topics(merged_lines)

    parts: list[EngineeringSyllabusPart] = []
    current_part_title: str | None = None
    current_part_topics: list[str] = []

    def _flush_current_part() -> None:
        nonlocal current_part_title, current_part_topics
        if current_part_title and current_part_topics:
            parts.append(
                {
                    "part_title": current_part_title,
                    "subtopic_titles": current_part_topics,
                }
            )
        current_part_title = None
        current_part_topics = []

    for line in merged_lines:
        clean = line.strip()
        if not clean:
            continue

        embedded_matches = _find_valid_embedded_part_matches(
            clean,
            allow_spurious_part_words=current_part_title is not None,
        )
        segments = _iter_engineering_part_segments(clean)
        if len(segments) == 1 and segments[0][0] is None:
            if embedded_matches and current_part_title:
                prefix = clean[: embedded_matches[0].start()].strip(" .,;")
                if prefix:
                    current_part_topics.extend(_split_comma_separated_topics(prefix))
                _flush_current_part()
                segments = _split_line_at_embedded_parts(clean, embedded_matches)
            elif embedded_matches and not current_part_title:
                segments = _split_line_at_embedded_parts(clean, embedded_matches)
            else:
                current_part_topics.extend(_split_comma_separated_topics(segments[0][1]))
                continue

        for part_title, topic_text in segments:
            if part_title is None:
                current_part_topics.extend(_split_comma_separated_topics(topic_text))
                continue
            if _is_engineering_inline_part_continuation(part_title):
                continuation = part_title
                if topic_text:
                    continuation = f"{continuation}: {topic_text}"
                current_part_topics.extend(_split_comma_separated_topics(continuation))
                continue
            _flush_current_part()
            current_part_title = part_title
            current_part_topics = _split_comma_separated_topics(topic_text) if topic_text else []

    _flush_current_part()

    if parts:
        return parts, []

    return None, _flat_syllabus_topics(merged_lines)


def _flatten_engineering_syllabus_subtopics(unit: EngineeringSyllabusUnit) -> list[str]:
    parts = unit.get("parts")
    if parts:
        flattened: list[str] = []
        for part in parts:
            flattened.extend(part["subtopic_titles"])
        return flattened
    return unit.get("subtopic_titles", [])


def _repair_engineering_unit_titles(units: list[EngineeringSyllabusUnit], *, needs_repair: bool) -> None:
    if not needs_repair:
        return
    roman_tokens = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
    for position, unit in enumerate(units):
        token = roman_tokens[position] if position < len(roman_tokens) else str(position + 1)
        rest = re.sub(r"^Unit\s+[IVXLCDM\d]+\s*", "", unit["unit_title"], flags=re.I).strip()
        unit["unit_title"] = f"Unit {token} {rest}".strip() if rest else f"Unit {token}"


def _parse_engineering_syllabus_structure_v2(
    pages: list[PageText],
    *,
    allow_arabic_unit_header: bool = True,
) -> list[EngineeringSyllabusUnit]:
    raw_blocks: list[tuple[int | None, str, list[EngineeringSyllabusPart] | None, list[str]]] = []
    current_title: str | None = None
    current_index: int | None = None
    body_lines: list[tuple[str, bool]] = []

    def _flush_body() -> None:
        nonlocal current_title, current_index, body_lines
        if current_title is None:
            body_lines = []
            return
        parts, flat_topics = _parse_engineering_syllabus_unit_body(body_lines)
        raw_blocks.append((current_index, current_title, parts, flat_topics))
        body_lines = []

    for page in pages:
        for line, is_bold in _iter_engineering_syllabus_lines(page):
            header = _match_engineering_syllabus_unit_header(
                line,
                allow_arabic=allow_arabic_unit_header,
            )
            if header is not None:
                _flush_body()
                current_index, current_title = header
                continue
            if current_title is not None and line.strip():
                body_lines.append((line.strip(), is_bold))
    _flush_body()

    if len(raw_blocks) < 2:
        return []

    parsed_indices = [index for index, _, _, _ in raw_blocks]
    unique_indices = {index for index in parsed_indices if index is not None}
    index_counts = Counter(index for index in parsed_indices if index is not None)
    max_repeat = max(index_counts.values(), default=0)
    needs_repair = (
        len(unique_indices) < max(2, len(raw_blocks) // 2)
        or len(unique_indices) == 1
        or max_repeat >= 3
    )

    units: list[EngineeringSyllabusUnit] = []
    for position, (index, title, parts, flat_topics) in enumerate(raw_blocks):
        unit_index = position + 1 if needs_repair else (index if index is not None else position + 1)
        unit: EngineeringSyllabusUnit = {"unit_title": title}
        if parts:
            unit["parts"] = parts
            unit["subtopic_titles"] = _flatten_engineering_syllabus_part_topics(parts)
        else:
            subtopic_titles = flat_topics
            if not subtopic_titles:
                subtopic_titles = _engineering_syllabus_topic_titles(title) or [title[:80]]
            unit["subtopic_titles"] = subtopic_titles
        if unit_index != index:
            token = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")[
                unit_index - 1
            ] if 1 <= unit_index <= 12 else str(unit_index)
            rest = re.sub(r"^Unit\s+[IVXLCDM\d]+\s*", "", title, flags=re.I).strip()
            unit["unit_title"] = f"Unit {token} {rest}".strip() if rest else f"Unit {token}"
        units.append(unit)

    _repair_engineering_unit_titles(units, needs_repair=needs_repair)
    return units


def _flatten_engineering_syllabus_part_topics(parts: list[EngineeringSyllabusPart] | None) -> list[str]:
    if not parts:
        return []
    flattened: list[str] = []
    for part in parts:
        flattened.extend(part["subtopic_titles"])
    return flattened


def _engineering_syllabus_topic_titles(
    body: str,
    *,
    max_sections: int = 8,
    min_chars: int = 12,
) -> list[str]:
    body = body.strip()
    if not body:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in body.splitlines() if line.strip()]

    topics: list[str] = []
    for paragraph in paragraphs:
        title = re.sub(r"\s+", " ", paragraph.splitlines()[0].strip())
        if len(title) >= min_chars:
            topics.append(title[:160])
        if len(topics) >= max_sections:
            break

    if not topics and body:
        fallback = re.sub(r"\s+", " ", body)[:80].strip()
        if fallback:
            topics = [fallback]
    return topics


def _repair_engineering_unit_indices(
    raw_blocks: list[tuple[int | None, str, list[str]]],
) -> list[tuple[int, str, list[str]]]:
    if not raw_blocks:
        return []

    parsed_indices = [index for index, _, _ in raw_blocks]
    unique_indices = {index for index in parsed_indices if index is not None}
    needs_repair = len(unique_indices) < max(2, len(raw_blocks) // 2) or len(unique_indices) == 1

    repaired: list[tuple[int, str, list[str]]] = []
    for position, (index, title, topics) in enumerate(raw_blocks):
        unit_index = position + 1 if needs_repair else (index if index is not None else position + 1)
        repaired.append((unit_index, title, topics))
    return repaired


def _parse_engineering_syllabus_structure(
    pages: list[PageText],
) -> list[EngineeringSyllabusUnit]:
    """Parse engineering syllabus pages into unit titles and subtopic lists for structure import."""
    try:
        return _parse_engineering_syllabus_structure_v2(pages)
    except Exception:
        logger.debug("Engineering syllabus structure parse failed", exc_info=True)
        return []


def _parse_engineering_syllabus_unit_blocks(
    pages: list[PageText],
) -> list[tuple[int, str, list[str]]] | None:
    """Parse Roman/dash UNIT blocks from engineering syllabi without page numbers."""
    try:
        parsed_units = _parse_engineering_syllabus_structure_v2(
            pages,
            allow_arabic_unit_header=False,
        )
    except Exception:
        logger.debug("Engineering syllabus unit block parse failed", exc_info=True)
        return None
    if len(parsed_units) < 2:
        return None

    blocks: list[tuple[int, str, list[str]]] = []
    for position, unit in enumerate(parsed_units):
        header = _match_engineering_unit_header(unit["unit_title"])
        unit_index = header[0] if header and header[0] is not None else position + 1
        topics = unit.get("subtopic_titles") or []
        if not topics:
            topics = _engineering_syllabus_topic_titles(unit["unit_title"]) or [unit["unit_title"][:80]]
        blocks.append((unit_index, unit["unit_title"], topics))
    return blocks


def _raw_outline_from_engineering_syllabus(pages: list[PageText]) -> DocumentOutline | None:
    parsed_units = _parse_engineering_syllabus_unit_blocks(pages)
    if not parsed_units:
        return None

    units: list[OutlineUnit] = []
    for unit_index, title, topic_titles in parsed_units:
        unit_page = unit_index - 1
        sections = [
            OutlineSection(title=topic, page_start=unit_page, page_end=unit_page)
            for topic in topic_titles
        ]
        if not sections:
            sections = [OutlineSection(title=title, page_start=unit_page, page_end=unit_page)]
        units.append(
            OutlineUnit(
                id=str(unit_index),
                title=title,
                page_start=unit_page,
                page_end=unit_page,
                sections=sections,
            )
        )

    page_count = max(len(units), max(unit.page_end for unit in units) + 1)
    outline = DocumentOutline(
        document="",
        course="",
        page_index_base=0,
        page_count=page_count,
        units=units,
        extraction_method="syllabus_block",
    )
    return outline if _section_count(outline) >= 2 else None


def _finish_engineering_syllabus_outline(
    raw: DocumentOutline,
) -> tuple[DocumentOutline | None, OutlineGranularity | None, OutlineQuality | None]:
    if len(raw.units) < 2:
        return None, None, None
    if not all(unit.sections for unit in raw.units):
        return None, None, None
    if _section_count(raw) < 2:
        return None, None, None

    raw.extraction_method = "syllabus_block"
    granularity: OutlineGranularity = "chapter" if len(raw.units) >= 3 else "section"
    quality = outline_quality_score(raw, granularity, syllabus_block=True)
    if quality == "low":
        return None, None, None
    return raw, granularity, quality


def _raw_outline_from_syllabus_no_page(pages: list[PageText]) -> DocumentOutline | None:
    """Build a flat bookmark-style outline from body UNIT X.Y anchors when TOC has no page nums."""
    parsed_units = _parse_syllabus_units_no_page_numbers(pages)
    if not parsed_units or len(parsed_units) < 3:
        return None

    entries: list[tuple[int, str, int]] = []
    for page in pages:
        if page.page <= 2:
            continue
        page_index = _page_index_from_page_text(page)
        for line in page.text.splitlines():
            clean = line.strip()
            if not clean:
                continue
            if _SUBUNIT_HEADING_RE.match(clean) or _SUBSECTION_NUMERIC_TITLE_RE.match(clean):
                entries.append((1, clean, page_index))

    if len(entries) < 2:
        for _major, _title, subsections in parsed_units:
            for subsection in subsections:
                entries.append((1, subsection, 0))

    if len(entries) < 2:
        return None

    entries.sort(key=lambda item: (item[2], item[1]))
    page_count = max((page.page for page in pages), default=1)
    return _build_raw_outline_from_parsed(
        entries,
        page_count=page_count,
        document="",
    )


def _section_span(section: OutlineSection) -> int:
    return section.page_end - section.page_start + 1


def _clone_units(units: list[OutlineUnit]) -> list[OutlineUnit]:
    return [
        OutlineUnit(
            id=unit.id,
            title=unit.title,
            page_start=unit.page_start,
            page_end=unit.page_end,
            sections=[
                OutlineSection(
                    title=section.title,
                    page_start=section.page_start,
                    page_end=section.page_end,
                )
                for section in unit.sections
            ],
        )
        for unit in units
    ]


def _merge_short_sections(units: list[OutlineUnit], *, min_span: int = _MIN_SECTION_SPAN) -> None:
    for unit in units:
        if not unit.sections:
            continue
        merged: list[OutlineSection] = []
        for section in unit.sections:
            if (
                merged
                and _section_span(section) < min_span
                and _parse_subsection_heading_line(section.title) is None
            ):
                prev = merged[-1]
                merged[-1] = OutlineSection(
                    title=prev.title,
                    page_start=prev.page_start,
                    page_end=max(prev.page_end, section.page_end),
                )
            else:
                merged.append(section)
        unit.sections = merged


def _merge_smallest_section(units: list[OutlineUnit]) -> bool:
    target: tuple[int, int, int] | None = None
    for unit_index, unit in enumerate(units):
        for section_index, section in enumerate(unit.sections):
            span = _section_span(section)
            if target is None or span < target[2]:
                target = (unit_index, section_index, span)
    if target is None:
        return False
    unit_index, section_index, _ = target
    sections = units[unit_index].sections
    if len(sections) <= 1:
        return False
    if section_index < len(sections) - 1:
        left, right = sections[section_index], sections[section_index + 1]
        sections[section_index] = OutlineSection(left.title, left.page_start, right.page_end)
        del sections[section_index + 1]
    else:
        left, right = sections[section_index - 1], sections[section_index]
        sections[section_index - 1] = OutlineSection(left.title, left.page_start, right.page_end)
        del sections[section_index]
    return True


def _merge_smallest_unit(units: list[OutlineUnit]) -> bool:
    if len(units) <= 1:
        return False
    merge_index = 0
    merge_size = len(units[0].sections) + len(units[1].sections)
    for index in range(len(units) - 1):
        size = len(units[index].sections) + len(units[index + 1].sections)
        if size < merge_size:
            merge_size = size
            merge_index = index
    left, right = units[merge_index], units[merge_index + 1]
    merged = OutlineUnit(
        id=left.id,
        title=left.title,
        page_start=min(left.page_start, right.page_start),
        page_end=max(left.page_end, right.page_end),
        sections=list(left.sections) + list(right.sections),
    )
    units[merge_index : merge_index + 2] = [merged]
    for index, unit in enumerate(units, start=1):
        unit.id = str(index)
    return True


def normalize_outline(outline: DocumentOutline) -> tuple[DocumentOutline, OutlineGranularity]:
    """Post-process extracted outline: merge tiny sections, cap unit/section counts."""
    units = _clone_units(outline.units)
    _merge_short_sections(units)
    while _section_count(DocumentOutline("", "", 0, 0, units)) > _MAX_SECTIONS_CAP:
        if not _merge_smallest_section(units):
            break
    while len(units) > _MAX_UNITS_CAP:
        if not _merge_smallest_unit(units):
            break
    _finalize_unit_ranges(units)
    normalized = _clone_outline_with_units(outline, units)
    granularity: OutlineGranularity = (
        "chapter" if _MIN_UNIT_COUNT <= len(units) <= _MAX_UNITS_CAP else "section"
    )
    return normalized, granularity


def outline_quality_score(
    outline: DocumentOutline,
    granularity: OutlineGranularity,
    *,
    is_auto_stub: bool = False,
    syllabus_block: bool = False,
) -> OutlineQuality:
    if syllabus_block:
        if len(outline.units) < 2:
            return "low"
        if len(outline.units) >= 3 and all(unit.sections for unit in outline.units):
            return "medium"
        if len(outline.units) >= 2 and all(unit.sections for unit in outline.units):
            return "medium"
        return "low"
    if is_auto_stub or granularity == "page_stub" or is_page_bucket_outline(outline):
        return "low"
    section_total = _section_count(outline)
    if section_total < _MIN_UNIT_COUNT:
        return "low"
    one_page_sections = sum(
        1 for unit in outline.units for section in unit.sections if _section_span(section) < 2
    )
    avg_span = (
        sum(_section_span(section) for unit in outline.units for section in unit.sections)
        / max(section_total, 1)
    )
    if (
        _MIN_UNIT_COUNT <= len(outline.units) <= _MAX_UNITS_CAP
        and section_total >= 2
        and avg_span >= _MIN_SECTION_SPAN
        and granularity == "chapter"
    ):
        return "high"
    if section_total > _MAX_SECTIONS_CAP or one_page_sections > section_total // 2 or granularity == "section":
        return "medium"
    return "medium"


def _extract_headings_from_page_dict(page_dict: dict[str, Any], page_index: int) -> list[tuple[str, int]]:
    sizes: list[float] = []
    raw_lines: list[tuple[str, float, bool]] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(str(span.get("text", "")) for span in spans).strip()
            if len(text) < 3 or len(text) > 180:
                continue
            max_size = max(float(span.get("size", 0)) for span in spans)
            is_bold = any("bold" in str(span.get("font", "")).lower() for span in spans)
            sizes.append(max_size)
            raw_lines.append((text, max_size, is_bold))

    if not sizes:
        return []
    median = sorted(sizes)[len(sizes) // 2]
    headings: list[tuple[str, int]] = []
    for text, max_size, is_bold in raw_lines:
        numbered = _is_chapter_marker(text) or _NUMBERED_HEADING_RE.match(text)
        prominent = max_size >= median * 1.12 or is_bold
        if numbered or (prominent and len(text.split()) <= 14):
            headings.append((text, page_index))
    return headings


def extract_outline_from_headings(
    path: Path,
    pages: list[PageText] | None = None,
) -> DocumentOutline | None:
    """Detect numbered/large-font headings in body pages (skip first 2 front-matter pages)."""
    doc = fitz.open(path)
    try:
        page_count = len(doc)
        if page_count <= 0:
            return None
        entries: list[tuple[str, int]] = []
        for page_index in range(min(2, page_count), page_count):
            page_dict = doc[page_index].get_text("dict")
            entries.extend(_extract_headings_from_page_dict(page_dict, page_index))
        if len(entries) < 3:
            return None
        flat: list[tuple[str, int, int]] = []
        for index, (title, page_start) in enumerate(entries):
            if index + 1 < len(entries):
                page_end = max(page_start, entries[index + 1][1] - 1)
            else:
                page_end = max(page_start, page_count - 1)
            flat.append((title, page_start, page_end))
        chapter_indices = [index for index, (title, _, _) in enumerate(flat) if _is_chapter_marker(title)]
        if len(chapter_indices) >= 3:
            units = _rollup_flat_by_chapters(flat, page_count, chapter_indices)
        else:
            sections = [
                OutlineSection(title=title, page_start=page_start, page_end=page_end)
                for title, page_start, page_end in flat
            ]
            units = [
                OutlineUnit(
                    id="1",
                    title="Contents",
                    page_start=sections[0].page_start,
                    page_end=sections[-1].page_end,
                    sections=sections,
                )
            ]
        _finalize_unit_ranges(units)
        outline = DocumentOutline(
            document=path.name,
            course="",
            page_index_base=0,
            page_count=page_count,
            units=units,
        )
        return outline if validate_extracted_outline(outline) else None
    finally:
        doc.close()


def _finish_extracted_outline(
    raw: DocumentOutline,
    toc_entries: list[tuple[int, str, int]] | None = None,
    *,
    pages: list[PageText] | None = None,
) -> tuple[DocumentOutline | None, OutlineGranularity | None, OutlineQuality | None]:
    rolled, chapter_gran = normalize_outline_chapters(raw, toc_entries=toc_entries)
    candidate = rolled if rolled is not None else raw
    syllabus_merge = _apply_syllabus_unit_merge(candidate, pages)
    if syllabus_merge is not None:
        candidate, chapter_gran = syllabus_merge
    if not validate_extracted_outline(candidate):
        return None, None, None
    normalized, granularity = normalize_outline(candidate)
    if chapter_gran == "chapter" and granularity == "section" and len(normalized.units) <= _MAX_UNITS_CAP:
        granularity = "chapter"
    if not validate_extracted_outline(normalized):
        return None, None, None
    if _too_granular_without_chapters(normalized):
        return None, None, None
    quality = outline_quality_score(normalized, granularity)
    return normalized, granularity, quality


def extract_outline_from_bookmarks(path: Path) -> DocumentOutline | None:
    """Build outline from PDF bookmarks (includes chapter normalization)."""
    outline, _granularity, _quality = extract_outline_from_pdf(path)
    return outline


def extract_outline_from_text_toc(
    pages: list[PageText],
    *,
    max_pages: int = _TEXT_TOC_MAX_PAGES,
) -> DocumentOutline | None:
    """Scan early pages for a textual table of contents (includes chapter normalization)."""
    outline, _granularity, _quality = extract_outline_from_pdf(
        Path("__synthetic__.pdf"),
        pages=pages[:max_pages],
    )
    return outline


def extract_outline_from_pdf(
    path: Path,
    *,
    pages: list[PageText] | None = None,
) -> tuple[DocumentOutline | None, OutlineGranularity | None, OutlineQuality | None]:
    """Try bookmarks → text TOC → body headings; normalize and score quality."""
    pages_provided = pages is not None
    if pages is None and path.name != "__synthetic__.pdf":
        extraction = extract_pdf(path)
        pages = extraction.pages

    if not pages_provided and path.name != "__synthetic__.pdf":
        raw, toc_entries = _raw_outline_from_bookmarks(path)
        if raw is not None:
            finished = _finish_extracted_outline(raw, toc_entries, pages=pages)
            if finished[0] is not None:
                return finished

    if pages is not None:
        eng_raw = _raw_outline_from_engineering_syllabus(pages)
        if eng_raw is not None:
            finished = _finish_engineering_syllabus_outline(eng_raw)
            if finished[0] is not None:
                return finished

        raw = _raw_outline_from_text_toc(pages)
        if raw is None:
            raw = _raw_outline_from_syllabus_no_page(pages)
        if raw is not None:
            finished = _finish_extracted_outline(raw, pages=pages)
            if finished[0] is not None:
                return finished

    if not pages_provided and path.name != "__synthetic__.pdf":
        raw = extract_outline_from_headings(path, pages)
        if raw is not None:
            finished = _finish_extracted_outline(raw, pages=pages)
            if finished[0] is not None:
                return finished

    return None, None, None
