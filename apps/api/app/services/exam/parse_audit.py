"""Forensic exam-parse audit (SP-062a) — measure only, no parser fixes."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Document, ExamQuestion
from app.services.exam.ou_chemistry import detect_ou_paper_header, split_ou_bundle_text
from app.services.exam.pyq_formats import detect_format, has_part_sections, is_compulsory
from app.services.exam.pyq_parser import ExamQuestionDraft, parse_exam_questions_from_pages
from app.services.exam.reference_report import (
    _base_question_number,
    _extract_paper_code,
    is_subpart_row,
    load_golden_reference,
)
from app.services.exam.topic_frequency import _READABLE_CHAR_THRESHOLD
from app.services.pdf_extract import PageText

_HERE = Path(__file__).resolve()


def _repo_root() -> Path:
    for parent in _HERE.parents:
        if (parent / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json").exists():
            return parent
    return _HERE.parents[5]


REPO_ROOT = _repo_root()
DEFAULT_GOLDEN_PATH = REPO_ROOT / "docs" / "reports" / "CHEMISTRY_GOLDEN_REFERENCE.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "reports" / "CHEMISTRY_PARSE_AUDIT.md"

_LOOSE_CODE = re.compile(
    r"\b([ED][-–—\s]?\d{4}\s*/\s*[ON0](?:\s*/\s*BL)?|\b\d{5}\b)",
    re.IGNORECASE,
)
_CODE_NO_LABEL = re.compile(r"Code\s*No\.?", re.IGNORECASE)
_PAPER_START = re.compile(
    r"FACULTY\s+OF|BS\s*204|Subject\s*:|Max\.?\s*Marks|B\.E\.",
    re.IGNORECASE,
)

DROP_REASONS = (
    "format_skip",
    "unreadably_short",
    "no_code_no",
    "no_part_header",
)


@dataclass
class PageAudit:
    page: int
    document: str
    char_count: int
    native_char_count: int | None
    extract_source: str  # native | ocr | unknown
    detect_format: str
    has_code_no: bool
    has_part_header: bool
    codes_on_page: list[str]
    drop_reasons: list[str]


@dataclass
class PaperSectionAudit:
    index: int
    extracted_code: str | None
    paper_label: str | None
    detect_format: str
    char_count: int
    has_part_header: bool
    drop_reasons: list[str]
    draft_rows: int
    draft_mains: int
    draft_subs: int


@dataclass
class GoldenCodeAudit:
    code: str
    session: str
    year: str
    paper_format: str
    golden_main: int
    golden_sub: int
    match: str  # exact | fuzzy | missing
    matched_code: str | None
    match_source: str | None
    draft_rows: int
    draft_mains: int
    draft_subs: int
    notes: list[str] = field(default_factory=list)


@dataclass
class ParseAuditResult:
    course_id: str
    golden_papers: int
    golden_mains: int
    golden_subs: int
    db_question_rows: int
    db_paper_codes: list[str]
    replay_draft_rows: int
    replay_mains: int
    replay_subs: int
    page_source: str
    pages: list[PageAudit]
    sections: list[PaperSectionAudit]
    codes: list[GoldenCodeAudit]
    drop_counts: dict[str, int]
    papers_found: list[str]
    papers_missing: list[str]
    evidence: list[str]


def normalize_paper_code(code: str | None) -> str | None:
    if not code:
        return None
    cleaned = code.upper().replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(r"^([ED])(\d)", r"\1-\2", cleaned)
    cleaned = re.sub(r"/0(/|$)", r"/O\1", cleaned)
    return cleaned or None


def extract_codes_from_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _LOOSE_CODE.finditer(text):
        normalized = normalize_paper_code(match.group(1))
        if normalized and normalized not in seen:
            seen.add(normalized)
            found.append(normalized)
    header = detect_ou_paper_header(text)
    header_code = normalize_paper_code(header.code)
    if header_code and header_code not in seen:
        found.append(header_code)
    return found


def _code_stem(code: str) -> str:
    normalized = normalize_paper_code(code) or ""
    return re.sub(r"/BL$", "", normalized)


def _similarity(left: str, right: str) -> float:
    a = normalize_paper_code(left) or ""
    b = normalize_paper_code(right) or ""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def match_golden_codes(
    extracted_codes: list[str],
    golden_codes: list[str],
) -> dict[str, dict[str, str | None]]:
    """1:1 assign extracted codes to golden codes. Values: match, matched_code."""
    remaining = list(dict.fromkeys(c for c in (normalize_paper_code(x) for x in extracted_codes) if c))
    assigned: dict[str, dict[str, str | None]] = {}

    for golden in golden_codes:
        target = normalize_paper_code(golden) or golden
        if target in remaining:
            assigned[golden] = {"match": "exact", "matched_code": target}
            remaining.remove(target)

    for golden in golden_codes:
        if golden in assigned:
            continue
        target = normalize_paper_code(golden) or golden
        best_code: str | None = None
        best_score = 0.0
        for candidate in remaining:
            score = _similarity(candidate, target)
            stem_ok = _code_stem(candidate) == _code_stem(target)
            same_stem_goldens = [
                g
                for g in golden_codes
                if g not in assigned and _code_stem(g) == _code_stem(target)
            ]
            if stem_ok and len(same_stem_goldens) > 1 and candidate != target:
                continue
            if (score >= 0.86 or (stem_ok and score >= 0.75)) and score > best_score:
                best_code = candidate
                best_score = score
        if best_code:
            assigned[golden] = {"match": "fuzzy", "matched_code": best_code}
            remaining.remove(best_code)
        else:
            assigned[golden] = {"match": "missing", "matched_code": None}
    return assigned


def draft_counts(drafts: list[ExamQuestionDraft] | list[Any]) -> tuple[int, int, int]:
    rows = len(drafts)
    subs = sum(1 for draft in drafts if is_subpart_row(getattr(draft, "question_number", None)))
    bases = {
        _base_question_number(getattr(draft, "question_number", None))
        for draft in drafts
        if _base_question_number(getattr(draft, "question_number", None))
    }
    return rows, len(bases), subs


def _looks_like_paper_start(text: str) -> bool:
    sample = text[:1500]
    return bool(_PAPER_START.search(sample) or _CODE_NO_LABEL.search(sample))


def classify_page_drops(
    *,
    text: str,
    char_count: int,
    fmt: str,
) -> list[str]:
    reasons: list[str] = []
    if char_count < _READABLE_CHAR_THRESHOLD:
        reasons.append("unreadably_short")
    if fmt == "skip":
        reasons.append("format_skip")
    paper_start = _looks_like_paper_start(text)
    has_code = detect_ou_paper_header(text).code is not None or bool(extract_codes_from_text(text))
    if paper_start and not has_code:
        reasons.append("no_code_no")
    if (
        paper_start
        and fmt != "continuation"
        and not has_part_sections(text)
        and not is_compulsory(text)
    ):
        reasons.append("no_part_header")
    return reasons


def classify_section_drops(header_code: str | None, text: str, fmt: str) -> list[str]:
    reasons: list[str] = []
    if fmt == "skip":
        reasons.append("format_skip")
    if len(text.strip()) < _READABLE_CHAR_THRESHOLD:
        reasons.append("unreadably_short")
    if header_code is None:
        reasons.append("no_code_no")
    if fmt != "continuation" and not has_part_sections(text) and not is_compulsory(text):
        reasons.append("no_part_header")
    return reasons


def _assign_extract_source(
    *,
    used_ocr: bool,
    native_char_count: int | None,
    stored_char_count: int,
) -> str:
    if used_ocr:
        return "ocr"
    if native_char_count is None:
        return "unknown"
    if native_char_count <= _READABLE_CHAR_THRESHOLD and stored_char_count > native_char_count:
        return "ocr"
    return "native"


def _native_pages_from_pdf(path: Path) -> list[PageText]:
    import fitz

    doc = fitz.open(path)
    pages: list[PageText] = []
    for index in range(len(doc)):
        text = (doc[index].get_text("text", sort=True) or "").strip()
        pages.append(PageText(page=index + 1, text=text, char_count=len(text), used_ocr=False))
    doc.close()
    return pages


def pages_from_chunks(chunks: list[Chunk]) -> list[PageText]:
    by_page: dict[int, list[str]] = defaultdict(list)
    for chunk in sorted(chunks, key=lambda row: (row.page, row.chunk_index)):
        if chunk.text:
            by_page[chunk.page].append(chunk.text)
    pages: list[PageText] = []
    for page_no, texts in sorted(by_page.items()):
        merged = "\n".join(texts).strip()
        pages.append(PageText(page=page_no, text=merged, char_count=len(merged), used_ocr=False))
    return pages


def load_document_pages(document: Document, chunks: list[Chunk]) -> tuple[list[PageText], str]:
    """Prefer ingested chunk text + native PDF probe (no OCR). Fall back to native-only PDF."""
    stored = {page.page: page for page in pages_from_chunks(chunks)}
    pdf_path = Path(document.file_path) if document.file_path else None
    if pdf_path and pdf_path.is_file():
        native_pages = _native_pages_from_pdf(pdf_path)
        merged: list[PageText] = []
        for native in native_pages:
            stored_page = stored.get(native.page)
            stored_text = stored_page.text if stored_page else ""
            stored_chars = stored_page.char_count if stored_page else 0
            if stored_chars > native.char_count:
                text = stored_text
                char_count = stored_chars
                used_ocr = native.char_count <= _READABLE_CHAR_THRESHOLD
            else:
                text = native.text
                char_count = native.char_count
                used_ocr = False
            page = PageText(page=native.page, text=text, char_count=char_count, used_ocr=used_ocr)
            page.metadata["native_char_count"] = native.char_count
            merged.append(page)
        extra_pages = [stored[page] for page in stored if page not in {p.page for p in merged}]
        merged.extend(extra_pages)
        merged.sort(key=lambda page: page.page)
        source = "pdf+chunks" if stored else "pdf-native"
        return merged, source
    if stored:
        return list(stored.values()), "chunks"
    return [], "none"


def _drafts_for_code(drafts: list[ExamQuestionDraft], code: str) -> list[ExamQuestionDraft]:
    target = normalize_paper_code(code)
    matched: list[ExamQuestionDraft] = []
    for draft in drafts:
        label_code = normalize_paper_code(_extract_paper_code(draft.paper_label))
        if label_code and target and (
            label_code == target or _similarity(label_code, target) >= 0.86
        ):
            matched.append(draft)
    return matched


def audit_pages(
    pages: list[PageText],
    *,
    course_id: str,
    filename: str,
    golden: dict[str, Any],
    db_question_rows: int = 0,
    db_paper_codes: list[str] | None = None,
    page_source: str = "supplied",
    document_label: str = "",
) -> ParseAuditResult:
    golden_papers = list(golden.get("papers") or [])
    golden_codes = [row["code"] for row in golden_papers]
    meta = golden.get("meta") or {}

    page_audits: list[PageAudit] = []
    extracted_codes: list[str] = []
    drop_counts: dict[str, int] = {reason: 0 for reason in DROP_REASONS}

    for page in pages:
        fmt = detect_format(page.text)
        codes = extract_codes_from_text(page.text)
        extracted_codes.extend(codes)
        reasons = classify_page_drops(text=page.text, char_count=page.char_count, fmt=fmt)
        native_chars = page.metadata.get("native_char_count") if page.metadata else None
        extract_source = _assign_extract_source(
            used_ocr=page.used_ocr,
            native_char_count=native_chars if isinstance(native_chars, int) else None,
            stored_char_count=page.char_count,
        )
        page_audits.append(
            PageAudit(
                page=page.page,
                document=document_label or filename,
                char_count=page.char_count,
                native_char_count=native_chars if isinstance(native_chars, int) else None,
                extract_source=extract_source,
                detect_format=fmt,
                has_code_no=bool(codes) or detect_ou_paper_header(page.text).code is not None,
                has_part_header=has_part_sections(page.text),
                codes_on_page=codes,
                drop_reasons=reasons,
            )
        )
        for reason in reasons:
            drop_counts[reason] += 1

    drafts = parse_exam_questions_from_pages(
        pages=pages,
        document_id=uuid.uuid4(),
        course_id=course_id,
        filename=filename,
    )
    replay_rows, replay_mains, replay_subs = draft_counts(drafts)

    readable = [page for page in pages if page.char_count >= _READABLE_CHAR_THRESHOLD]
    merged = "\n\n".join(page.text for page in readable)
    raw_sections = split_ou_bundle_text(merged) if merged.strip() else []
    sections: list[PaperSectionAudit] = []
    for index, (header, text) in enumerate(raw_sections, start=1):
        fmt = detect_format(text)
        code = normalize_paper_code(header.code)
        reasons = classify_section_drops(code, text, fmt)
        section_probe = parse_exam_questions_from_pages(
            pages=[PageText(page=1, text=text, char_count=len(text))],
            document_id=uuid.uuid4(),
            course_id=course_id,
            filename=filename,
        )
        rows, mains, subs = draft_counts(section_probe)
        sections.append(
            PaperSectionAudit(
                index=index,
                extracted_code=code,
                paper_label=header.paper_label,
                detect_format=fmt,
                char_count=len(text),
                has_part_header=has_part_sections(text),
                drop_reasons=reasons,
                draft_rows=rows,
                draft_mains=mains,
                draft_subs=subs,
            )
        )
        if code:
            extracted_codes.append(code)

    matches = match_golden_codes(extracted_codes, golden_codes)
    code_audits: list[GoldenCodeAudit] = []
    papers_found: list[str] = []
    papers_missing: list[str] = []
    db_codes = [c for c in (normalize_paper_code(c) for c in (db_paper_codes or [])) if c]

    for row in golden_papers:
        code = row["code"]
        assignment = matches[code]
        matched = assignment["matched_code"]
        match_kind = assignment["match"] or "missing"
        related = _drafts_for_code(drafts, matched or code)
        rows, mains, subs = draft_counts(related)
        notes: list[str] = []
        if match_kind == "missing":
            papers_missing.append(code)
            notes.append("code not found in extracted page text or splitter headers")
        else:
            papers_found.append(code)
        if match_kind == "fuzzy":
            notes.append(f"fuzzy matched to extracted {matched}")
        db_hit = any(
            normalize_paper_code(db_code) == normalize_paper_code(code)
            or (matched and normalize_paper_code(db_code) == matched)
            for db_code in db_codes
        )
        if db_hit:
            notes.append("present on stored exam_questions.paper_label")
        elif match_kind != "missing":
            notes.append("found in extract; not present on stored paper_label")
        if rows == 0 and match_kind != "missing":
            notes.append("code seen but parser produced 0 drafts for this label")
        if rows and (mains < row["main"] or subs < row["sub"]):
            notes.append(
                f"under-count vs golden main {mains}/{row['main']} sub {subs}/{row['sub']}"
            )
        code_audits.append(
            GoldenCodeAudit(
                code=code,
                session=row.get("session", ""),
                year=str(row.get("year", "")),
                paper_format=row.get("format", ""),
                golden_main=int(row["main"]),
                golden_sub=int(row["sub"]),
                match=match_kind,
                matched_code=matched,
                match_source="extract" if match_kind != "missing" else None,
                draft_rows=rows,
                draft_mains=mains,
                draft_subs=subs,
                notes=notes,
            )
        )

    evidence = _build_evidence(
        db_question_rows=db_question_rows,
        replay_rows=replay_rows,
        replay_mains=replay_mains,
        replay_subs=replay_subs,
        golden_meta=meta,
        pages=page_audits,
        sections=sections,
        papers_found=papers_found,
        papers_missing=papers_missing,
        drop_counts=drop_counts,
    )

    return ParseAuditResult(
        course_id=course_id,
        golden_papers=int(meta.get("papers", len(golden_papers))),
        golden_mains=int(meta.get("main_questions", 151)),
        golden_subs=int(meta.get("subparts", 300)),
        db_question_rows=db_question_rows,
        db_paper_codes=sorted(set(db_codes)),
        replay_draft_rows=replay_rows,
        replay_mains=replay_mains,
        replay_subs=replay_subs,
        page_source=page_source,
        pages=page_audits,
        sections=sections,
        codes=code_audits,
        drop_counts=drop_counts,
        papers_found=papers_found,
        papers_missing=papers_missing,
        evidence=evidence,
    )


def _build_evidence(
    *,
    db_question_rows: int,
    replay_rows: int,
    replay_mains: int,
    replay_subs: int,
    golden_meta: dict[str, Any],
    pages: list[PageAudit],
    sections: list[PaperSectionAudit],
    papers_found: list[str],
    papers_missing: list[str],
    drop_counts: dict[str, int],
) -> list[str]:
    total_pages = len(pages)
    short_pages = [p for p in pages if "unreadably_short" in p.drop_reasons]
    skip_pages = [p for p in pages if "format_skip" in p.drop_reasons]
    no_code_pages = [p for p in pages if "no_code_no" in p.drop_reasons]
    no_part_pages = [p for p in pages if "no_part_header" in p.drop_reasons]
    ocr_pages = [p for p in pages if p.extract_source == "ocr"]
    native_pages = [p for p in pages if p.extract_source == "native"]
    section_no_code = [s for s in sections if "no_code_no" in s.drop_reasons]
    section_skip = [s for s in sections if "format_skip" in s.drop_reasons]
    section_no_part = [s for s in sections if "no_part_header" in s.drop_reasons]
    lines = [
        (
            f"Stored exam_questions rows={db_question_rows}; parser replay on the same "
            f"ingest pages produced drafts={replay_rows} (mains={replay_mains} "
            f"subs={replay_subs}). Golden target is {golden_meta.get('papers', 13)} papers / "
            f"{golden_meta.get('main_questions', 151)} mains / {golden_meta.get('subparts', 300)} sub-parts."
        ),
        (
            f"Page probe: {total_pages} pages "
            f"(native={len(native_pages)}, ocr={len(ocr_pages)}, "
            f"unknown={sum(1 for p in pages if p.extract_source == 'unknown')}). "
            f"Readable threshold is {_READABLE_CHAR_THRESHOLD} chars — "
            f"{len(short_pages)} page(s) unreadably short and excluded from the OU bundle merge."
        ),
        (
            f"OU splitter produced {len(sections)} paper section(s) vs golden 13. "
            f"Golden codes found={len(papers_found)} missing={len(papers_missing)}."
        ),
    ]
    if papers_missing:
        lines.append("Missing golden codes: " + ", ".join(papers_missing) + ".")
    if short_pages:
        sample = ", ".join(f"p{p.page}({p.char_count}c)" for p in short_pages[:8])
        extra = "" if len(short_pages) <= 8 else f" (+{len(short_pages) - 8} more)"
        lines.append(f"Unreadably short pages (evidence): {sample}{extra}.")
    if skip_pages:
        sample = ", ".join(f"p{p.page}/{p.detect_format}" for p in skip_pages[:8])
        lines.append(
            f"Format-skip pages={len(skip_pages)} (detect_format=skip): {sample}."
        )
    if no_code_pages:
        sample = ", ".join(f"p{p.page}" for p in no_code_pages[:8])
        lines.append(
            f"Paper-start pages with no parseable Code No={len(no_code_pages)}: {sample}."
        )
    if no_part_pages:
        sample = ", ".join(f"p{p.page}" for p in no_part_pages[:8])
        lines.append(
            f"Paper-start pages with no PART header and not compulsory={len(no_part_pages)}: {sample}."
        )
    if section_no_code or section_skip or section_no_part:
        lines.append(
            "Splitter section drops: "
            f"no_code_no={len(section_no_code)}, format_skip={len(section_skip)}, "
            f"no_part_header={len(section_no_part)}."
        )
    parsed_sections = [s for s in sections if s.draft_rows > 0]
    if parsed_sections:
        detail = "; ".join(
            f"{s.extracted_code or 'NO_CODE'}→{s.draft_rows} rows"
            for s in parsed_sections[:13]
        )
        lines.append(f"Drafts by splitter section: {detail}.")
    lines.append(
        "Drop-reason event counts (page-level): "
        + ", ".join(f"{name}={drop_counts[name]}" for name in DROP_REASONS)
        + "."
    )
    return lines


def merge_audit_results(results: list[ParseAuditResult], *, course_id: str) -> ParseAuditResult:
    if len(results) == 1:
        return results[0]
    if not results:
        golden = load_golden_reference(DEFAULT_GOLDEN_PATH)
        return audit_pages(
            [],
            course_id=course_id,
            filename="",
            golden=golden,
            page_source="none",
        )

    golden = load_golden_reference(DEFAULT_GOLDEN_PATH)
    golden_papers = list(golden.get("papers") or [])
    pages: list[PageAudit] = []
    sections: list[PaperSectionAudit] = []
    extracted_codes: list[str] = []
    drop_counts: dict[str, int] = {reason: 0 for reason in DROP_REASONS}
    db_rows = results[0].db_question_rows
    db_codes = list(results[0].db_paper_codes)
    replay_rows = sum(item.replay_draft_rows for item in results)
    replay_mains = sum(item.replay_mains for item in results)
    replay_subs = sum(item.replay_subs for item in results)
    sources = sorted({item.page_source for item in results})

    draft_by_code: dict[str, tuple[int, int, int]] = defaultdict(lambda: (0, 0, 0))
    for item in results:
        pages.extend(item.pages)
        for section in item.sections:
            sections.append(
                PaperSectionAudit(
                    index=len(sections) + 1,
                    extracted_code=section.extracted_code,
                    paper_label=section.paper_label,
                    detect_format=section.detect_format,
                    char_count=section.char_count,
                    has_part_header=section.has_part_header,
                    drop_reasons=section.drop_reasons,
                    draft_rows=section.draft_rows,
                    draft_mains=section.draft_mains,
                    draft_subs=section.draft_subs,
                )
            )
            if section.extracted_code:
                extracted_codes.append(section.extracted_code)
        for page in item.pages:
            extracted_codes.extend(page.codes_on_page)
            for reason in page.drop_reasons:
                drop_counts[reason] += 1
        for code_row in item.codes:
            prev = draft_by_code[code_row.code]
            draft_by_code[code_row.code] = (
                prev[0] + code_row.draft_rows,
                prev[1] + code_row.draft_mains,
                prev[2] + code_row.draft_subs,
            )

    matches = match_golden_codes(extracted_codes, [row["code"] for row in golden_papers])
    code_audits: list[GoldenCodeAudit] = []
    papers_found: list[str] = []
    papers_missing: list[str] = []
    first_notes = {row.code: row for row in results[0].codes}
    for row in golden_papers:
        code = row["code"]
        assignment = matches[code]
        match_kind = assignment["match"] or "missing"
        matched = assignment["matched_code"]
        rows, mains, subs = draft_by_code.get(code, (0, 0, 0))
        notes = list(first_notes.get(code).notes) if code in first_notes else []
        if match_kind == "missing":
            papers_missing.append(code)
        else:
            papers_found.append(code)
        code_audits.append(
            GoldenCodeAudit(
                code=code,
                session=row.get("session", ""),
                year=str(row.get("year", "")),
                paper_format=row.get("format", ""),
                golden_main=int(row["main"]),
                golden_sub=int(row["sub"]),
                match=match_kind,
                matched_code=matched,
                match_source="extract" if match_kind != "missing" else None,
                draft_rows=rows,
                draft_mains=mains,
                draft_subs=subs,
                notes=notes,
            )
        )

    evidence = _build_evidence(
        db_question_rows=db_rows,
        replay_rows=replay_rows,
        replay_mains=replay_mains,
        replay_subs=replay_subs,
        golden_meta=golden.get("meta") or {},
        pages=pages,
        sections=sections,
        papers_found=papers_found,
        papers_missing=papers_missing,
        drop_counts=drop_counts,
    )
    return ParseAuditResult(
        course_id=course_id,
        golden_papers=int((golden.get("meta") or {}).get("papers", 13)),
        golden_mains=int((golden.get("meta") or {}).get("main_questions", 151)),
        golden_subs=int((golden.get("meta") or {}).get("subparts", 300)),
        db_question_rows=db_rows,
        db_paper_codes=sorted(set(db_codes)),
        replay_draft_rows=replay_rows,
        replay_mains=replay_mains,
        replay_subs=replay_subs,
        page_source="+".join(sources),
        pages=pages,
        sections=sections,
        codes=code_audits,
        drop_counts=drop_counts,
        papers_found=papers_found,
        papers_missing=papers_missing,
        evidence=evidence,
    )


def audit_course(
    session: Session,
    course_id: str,
    *,
    golden_path: Path | None = None,
) -> ParseAuditResult:
    golden = load_golden_reference(golden_path or DEFAULT_GOLDEN_PATH)
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.course_id == course_id, Document.doc_kind == "past_paper")
            .order_by(Document.created_at)
        )
    )
    questions = list(
        session.scalars(select(ExamQuestion).where(ExamQuestion.course_id == course_id))
    )
    db_codes = [
        code
        for code in (_extract_paper_code(q.paper_label) for q in questions)
        if code
    ]

    if not documents:
        result = audit_pages(
            [],
            course_id=course_id,
            filename="",
            golden=golden,
            db_question_rows=len(questions),
            db_paper_codes=db_codes,
            page_source="none",
        )
        result.evidence.insert(
            0,
            f"No past_paper documents found for course_id={course_id}.",
        )
        return result

    per_doc: list[ParseAuditResult] = []
    for document in documents:
        chunks = list(
            session.scalars(select(Chunk).where(Chunk.document_id == document.id))
        )
        pages, source = load_document_pages(document, chunks)
        per_doc.append(
            audit_pages(
                pages,
                course_id=course_id,
                filename=document.filename,
                golden=golden,
                db_question_rows=len(questions),
                db_paper_codes=db_codes,
                page_source=source,
                document_label=document.filename,
            )
        )
    return merge_audit_results(per_doc, course_id=course_id)


def format_audit_markdown(result: ParseAuditResult) -> str:
    found_n = len(result.papers_found)
    missing_n = len(result.papers_missing)
    lines = [
        "# Chemistry parse forensic audit (SP-062a)",
        "",
        "Measure-only report. Parser / ingest code was not changed. "
        "Do not treat this as a 13/151/300 fix.",
        "",
        "## Summary",
        "",
        f"- Course: `{result.course_id}`",
        f"- Page source: `{result.page_source}`",
        f"- Golden: **{result.golden_papers} papers / {result.golden_mains} mains / {result.golden_subs} sub-parts**",
        f"- Stored `exam_questions` rows: **{result.db_question_rows}**",
        f"- Parser replay drafts: **{result.replay_draft_rows}** "
        f"(mains={result.replay_mains}, subs={result.replay_subs})",
        f"- papers_found: **{found_n}** — {', '.join(result.papers_found) or '(none)'}",
        f"- papers_missing: **{missing_n}** — {', '.join(result.papers_missing) or '(none)'}",
        f"- Stored paper codes: {', '.join(result.db_paper_codes) or '(none)'}",
        "",
        "## Why ~105 rows (evidence)",
        "",
    ]
    for item in result.evidence:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Drop reasons",
            "",
            "| Reason | Page-level events | Meaning |",
            "|---|---:|---|",
            f"| format_skip | {result.drop_counts['format_skip']} | `detect_format` returned skip |",
            f"| unreadably_short | {result.drop_counts['unreadably_short']} | char_count < {_READABLE_CHAR_THRESHOLD}; excluded from OU merge |",
            f"| no_code_no | {result.drop_counts['no_code_no']} | paper-start page/section with no parseable Code No |",
            f"| no_part_header | {result.drop_counts['no_part_header']} | paper-start without PART-A/B and not compulsory |",
            "",
            "## Per page",
            "",
            "| Doc | Page | chars | native_chars | native vs OCR | detect_format | Code No | PART | drops | codes |",
            "|---|---:|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for page in result.pages:
        lines.append(
            f"| {page.document} | {page.page} | {page.char_count} | "
            f"{page.native_char_count if page.native_char_count is not None else '—'} | "
            f"{page.extract_source} | {page.detect_format} | "
            f"{'yes' if page.has_code_no else 'no'} | "
            f"{'yes' if page.has_part_header else 'no'} | "
            f"{', '.join(page.drop_reasons) or '—'} | "
            f"{', '.join(page.codes_on_page) or '—'} |"
        )
    if not result.pages:
        lines.append("| — | — | 0 | — | — | — | — | — | no pages loaded | — |")

    lines.extend(
        [
            "",
            "## Splitter sections",
            "",
            "| # | code | format | chars | PART | drops | draft rows | mains | subs |",
            "|---|---|---|---:|---|---|---:|---:|---:|",
        ]
    )
    for section in result.sections:
        lines.append(
            f"| {section.index} | {section.extracted_code or '—'} | {section.detect_format} | "
            f"{section.char_count} | {'yes' if section.has_part_header else 'no'} | "
            f"{', '.join(section.drop_reasons) or '—'} | {section.draft_rows} | "
            f"{section.draft_mains} | {section.draft_subs} |"
        )
    if not result.sections:
        lines.append("| — | — | — | 0 | — | no sections | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Golden paper codes (13)",
            "",
            "| Code | Session | Fmt | Match | Extracted as | Golden main/sub | Draft main/sub/rows | Notes |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in result.codes:
        lines.append(
            f"| `{row.code}` | {row.session} | {row.paper_format} | **{row.match}** | "
            f"{row.matched_code or '—'} | {row.golden_main}/{row.golden_sub} | "
            f"{row.draft_mains}/{row.draft_subs}/{row.draft_rows} | "
            f"{'; '.join(row.notes) or '—'} |"
        )

    lines.extend(
        [
            "",
            "## papers_found / papers_missing",
            "",
            f"- papers_found ({found_n}): {', '.join(f'`{c}`' for c in result.papers_found) or '(none)'}",
            f"- papers_missing ({missing_n}): {', '.join(f'`{c}`' for c in result.papers_missing) or '(none)'}",
            "",
            "## Method",
            "",
            "- Replayed `parse_exam_questions_from_pages` / `split_ou_bundle_text` / `detect_format` without modifying them.",
            "- Page text comes from ingested chunks when present; native PDF text is probed without re-OCR.",
            "- A page is `ocr` when stored/chunk text is longer than native text at or below the readable threshold.",
            "- Code match: exact after normalize (`O`/`0`, whitespace); fuzzy via ratio ≥ 0.86. "
            "`E-5002/O` and `E-5002/O/BL` stay distinct.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_audit_report(result: ParseAuditResult, path: Path | None = None) -> Path:
    report_path = path or DEFAULT_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(format_audit_markdown(result), encoding="utf-8")
    return report_path


def result_as_dict(result: ParseAuditResult) -> dict[str, Any]:
    return asdict(result)
