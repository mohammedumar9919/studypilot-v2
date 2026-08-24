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

## Validate CLI

```powershell
cd C:\Projects\studypilot-v2\apps\api
python -m app.cli.exam_reference_report --validate --course PPL
python -m app.cli.exam_reference_report --validate --course chemistry
```

PPL uses `paper_count_source: labels` (no OU code labels). Core gate passes when stored `exam_questions` match seed-confirmed counts ± tolerances.

## Next slice

**SP-064e** — PPL subject pack + full parse → update golden counts from live DB (replace estimates).
