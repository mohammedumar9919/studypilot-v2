# PPL golden reference — derivation notes (SP-064c)

**File:** [PPL_GOLDEN_REFERENCE.json](./PPL_GOLDEN_REFERENCE.json)  
**Schema:** [golden_reference.schema.json](./golden_reference.schema.json)

## Sources

| Artifact | Role |
|----------|------|
| `eval/fixtures/ppl/ppl_pyq_seed.yaml` | Human-reviewed question → unit/section mapping (primary) |
| `eval/fixtures/ppl/ppl_outline.yaml` | Five-unit notes taxonomy (unit titles) |

## Confirmed counts (seed, page 3 only)

Derived by aggregating the 25 `questions:` entries in `ppl_pyq_seed.yaml` for **July 2021 Main & Backlog** (page 3):

| Metric | Value | Derivation |
|--------|-------|------------|
| **papers** | 1 | Single entry in `exam_papers:` |
| **main_questions** | 17 | Part A mains 1–10 (10) + Part B mains 11–17 (7) |
| **subparts** | 25 | One seed row per scorable prompt (10 Part A + 15 Part B sub-parts) |

### Unit subpart totals (seed `unit` id → outline title)

| Unit | Seed rows | Outline title |
|------|-----------|---------------|
| Unit 1 | 8 | Preliminary Concepts |
| Unit 2 | 3 | Data Types and Variables |
| Unit 3 | 1 | Subprograms and Blocks |
| Unit 4 | 9 | Abstract Data Types |
| Unit 5 | 4 | Functional Programming Languages |

### Top topics (seed `section_title` frequency)

1. Syntax and Semantics — 6  
2. Abstract Data Types & Object-Oriented Programming — 5  
3. Functional Programming Languages & Scripting Language — 4  
4. Exception Handling & Logic Programming Language — 4  
5. Expressions and Statements & Control Structures — 2  
6. Preliminary Concepts — 2  
7. Data Types and Variables — 1  
8. Subprograms and Blocks — 1  

## Estimates (Human Gate — not core validate targets)

| Field | Value | Status |
|-------|-------|--------|
| `estimates.total_questions_estimated_full_pdf` | **~50** | **ESTIMATE** from Phase 3C keyword heatmap note (`ppl_pyq_seed.yaml` + keyword matcher on remaining readable pages). Not confirmed mains/subparts split. |

Full `PPL previous papers.pdf` has **29/30 readable pages** after SP-043 OCR; only page 3 is seed-mapped in detail. **Do not treat ~50 as validate core gate** until SP-064e PPL parse populates `exam_questions`.

## Live vs golden (SP-064e — 2026-08-23)

| Metric | Golden (seed, page 3) | Live DB | Parser replay (full PDF) | Page-3 replay |
|--------|----------------------|---------|--------------------------|---------------|
| papers | 1 | 16 labels | 1 (seed label) | 1 |
| mains | 17 | 18 | 18 | 17 |
| subparts | 25 | 117 | 117 | **11** (under-count) |
| total rows | — | 377 | 377 | 22 |

**Core validate (`exam_reference_report --validate --course PPL`): FAIL** — expected. Golden targets **seed-confirmed page 3 only**; live DB holds the **full** `PPL previous papers.pdf` parse (~29 readable pages). Do **not** update golden counts without Human Gate.

### Root cause

1. **Scope mismatch:** `PPL_GOLDEN_REFERENCE.json` core gate is page-3 seed (17/25). Live `exam_questions` includes all readable pages → 117 subparts, 16 distinct `paper_label` values.
2. **Page-3 subpart gap:** Parser replay on golden page 3 yields 11 subparts vs seed 25 (22 draft rows). Generic regex misses nested Part B sub-prompts on native page 3; fix belongs in `PplPack.parse_pages` hints (future) or dedicated PPL grammar — **not** `pyq_parser` if-chains.
3. **PplPack wired:** `get_pack("PPL")` → `PplPack`; fixture paths delegated from pack; classify uses seed YAML + GenericPack structure fallback.

### User terminal — re-ingest (if parser hints added later)

```powershell
cd C:\Projects\studypilot-v2\apps\api
# Re-parse past_paper only (after parser changes):
python -m app.cli.ingest_document --course PPL --file "..\..\eval\fixtures\ppl\PPL previous papers.pdf" --doc-kind past_paper
python -m app.cli.exam_reference_report --validate --course PPL
python -m app.cli.exam_parse_audit --course PPL
```

### Parse audit

```powershell
python -m app.cli.exam_parse_audit --course PPL
```

Report: [PPL_PARSE_AUDIT.md](./PPL_PARSE_AUDIT.md)

## Validate CLI

```powershell
cd C:\Projects\studypilot-v2\apps\api
python -m app.cli.exam_reference_report --validate --course PPL
python -m app.cli.exam_reference_report --validate --course chemistry
```

PPL uses `paper_count_source: labels` (no OU code labels). Core gate passes when stored `exam_questions` match seed-confirmed counts ± tolerances **for the scoped corpus** (page 3 until full-PDF golden is Human-Gate approved).

## Status

**SP-064e DONE** — `PplPack` registered; validate/audit CLIs work for PPL. Core gate remains FAIL until golden scope aligns with live corpus or page-3 parse reaches 25 subparts.
