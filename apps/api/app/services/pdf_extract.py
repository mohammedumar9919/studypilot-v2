"""PyMuPDF text extraction with optional Tesseract OCR fallback."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz
import yaml

from app.config import settings

logger = logging.getLogger(__name__)


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
        if len(text.strip()) < threshold:
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


def _parse_outline_section(raw: dict[str, Any]) -> OutlineSection:
    return OutlineSection(
        title=str(raw["title"]),
        page_start=int(raw["page_start"]),
        page_end=int(raw["page_end"]),
    )


def load_outline(path: Path) -> DocumentOutline:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
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
        document=str(data.get("document", path.stem)),
        course=str(data.get("course", "")),
        page_index_base=int(data.get("page_index_base", 0)),
        page_count=int(data.get("page_count", 0)),
        units=units,
        front_matter=front_matter,
    )


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
