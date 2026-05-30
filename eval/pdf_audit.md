# PDF audit — Chemistry vs PPL (Phase 0 golden set)

## Summary recommendation

**Use PPL for Phase 0.** Chemistry notes are partially missing; Chemistry past papers are fully scanned with zero extractable text.

## File audit

| File | Pages | Extractable chars | Non-empty pages | Verdict |
|------|-------|-------------------|-----------------|---------|
| `engineering chemistry updated.pdf` | 69 | 85,235 | ~52 (pages 53–61 empty) | Notes OK for Units 1–2; Units 3–5 largely missing except composites (p62–69) |
| `OU QUESTION PAPERS.pdf` | 17 | **0** | **0/17** | Image-only scan — needs OCR before any PYQ eval |
| `PPL notes.pdf` | 94 | 217,033 | ~94 | Excellent text; clear 5-unit structure |
| `PPL previous papers.pdf` | 30 | 3,337 | **1/30** | Mostly scanned; one July 2021 paper (p3) fully readable |

## Ingest flags for Phase 1a

| Document | doc_kind | extraction_quality notes |
|----------|----------|--------------------------|
| PPL notes.pdf | notes | Good native text; MJCET header on every page (strip in chunk metadata) |
| PPL previous papers.pdf | past_paper | OCR fallback required for 29/30 pages; exclude from Study retrieval |
| engineering chemistry updated.pdf | notes | Partial — flag `extraction_quality.partial=true` |
| OU QUESTION PAPERS.pdf | past_paper | OCR mandatory; defer until Tesseract path validated |

## Hybrid deployment

Locked as **default** for Hyderabad pilots: local embeddings + OpenRouter generation via license proxy.
