"""Tests for PDF audit tier classification (SP-045a)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ingestion import ingest_document
from app.services.pdf_extract import (
    PdfAuditResult,
    audit_pdf,
    classify_audit_tier,
    reconcile_audit_tier,
    ExtractionResult,
)

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "ppl"
NOTES_PDF = FIXTURES / "PPL notes.pdf"
PAPERS_PDF = FIXTURES / "PPL previous papers.pdf"


def test_classify_audit_tier_native() -> None:
    assert classify_audit_tier(
        native_empty_ratio=0.05,
        multi_column_ratio=0.0,
        image_heavy_ratio=0.0,
    ) == "native"


def test_classify_audit_tier_ocr_scanned() -> None:
    assert classify_audit_tier(
        native_empty_ratio=0.9,
        multi_column_ratio=0.0,
        image_heavy_ratio=0.8,
    ) == "ocr"


def test_classify_audit_tier_layout_defer() -> None:
    assert classify_audit_tier(
        native_empty_ratio=0.1,
        multi_column_ratio=0.5,
        image_heavy_ratio=0.0,
    ) == "layout_defer"


def test_reconcile_audit_tier_upgrades_mixed_scan() -> None:
    audit = PdfAuditResult(
        tier="native",
        page_count=10,
        sampled_pages=10,
        native_empty_ratio=0.1,
        multi_column_ratio=0.0,
        image_heavy_ratio=0.0,
        avg_native_chars=400.0,
    )
    extraction = ExtractionResult(
        pages=[],
        page_count=10,
        total_chars=1000,
        nonempty_pages=10,
        ocr_pages=4,
        quality_flags={},
    )
    assert reconcile_audit_tier(audit, extraction) == "ocr"


def test_reconcile_audit_tier_preserves_layout_defer() -> None:
    audit = PdfAuditResult(
        tier="layout_defer",
        page_count=20,
        sampled_pages=12,
        native_empty_ratio=0.1,
        multi_column_ratio=0.5,
        image_heavy_ratio=0.0,
        avg_native_chars=250.0,
    )
    extraction = ExtractionResult(
        pages=[],
        page_count=20,
        total_chars=5000,
        nonempty_pages=18,
        ocr_pages=1,
        quality_flags={},
    )
    assert reconcile_audit_tier(audit, extraction) == "layout_defer"


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="Missing PPL notes fixture")
def test_audit_pdf_ppl_notes_is_native() -> None:
    audit = audit_pdf(NOTES_PDF)
    assert audit.tier == "native"
    assert audit.page_count == 94
    assert audit.native_empty_ratio < 0.2


@pytest.mark.skipif(not PAPERS_PDF.exists(), reason="Missing PPL past papers fixture")
def test_audit_pdf_ppl_papers_is_ocr() -> None:
    audit = audit_pdf(PAPERS_PDF)
    assert audit.tier == "ocr"
    assert audit.page_count == 30


@pytest.mark.skipif(not NOTES_PDF.exists(), reason="Missing PPL notes fixture")
def test_ingest_ppl_notes_sets_audit_tier(db_session) -> None:
    doc = ingest_document(
        db_session,
        file_path=NOTES_PDF,
        course_id="PPL",
        doc_kind="notes",
    )
    quality = doc.extraction_quality or {}
    assert quality.get("audit_tier") == "native"
    assert quality.get("audit_page_count") == 94


@pytest.mark.skipif(not PAPERS_PDF.exists(), reason="Missing PPL past papers fixture")
def test_ingest_ppl_papers_sets_audit_tier(db_session) -> None:
    doc = ingest_document(
        db_session,
        file_path=PAPERS_PDF,
        course_id="PPL",
        doc_kind="past_paper",
    )
    quality = doc.extraction_quality or {}
    assert quality.get("audit_tier") == "ocr"
