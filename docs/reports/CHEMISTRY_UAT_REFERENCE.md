# Chemistry UAT Reference Report

**Generated:** 2026-07-03  
**Purpose:** Baseline to compare against StudyPilot Exam Analytics UI for course `chemistry`.

## Source files (user-provided)

| File | Role |
|------|------|
| `C:\Users\Owner\Downloads\OU QUESTION PAPERS (1).pdf` | 13 past papers (user); 17 pages in PDF |
| `C:\Users\Owner\Downloads\WhatsApp Unknown 2026-06-09 at 2.11.11 AM\chemistry syllabus.pdf` | Syllabus (5 units) |

## Root cause — UI showed 0 concepts

- **119** `exam_questions` were parsed, but **`derive_exam_concepts` had never run** (course ingested before SP-060a hook or no re-ingest after Phase E).
- **Fix applied:** `python -m app.cli.derive_exam_concepts --course chemistry` → **230 concepts** (229 classified).
- **Code fix:** `GET .../exam/analytics` now lazy-backfills concepts when questions exist but concepts table is empty.

**Action for you:** Hard-refresh Exam Analytics (or click Refresh). You should see concepts, not "No classified concepts yet."

## Data hygiene notes (course `chemistry`)

| Document | doc_kind | Issue |
|----------|----------|-------|
| `OU QUESTION PAPERS (1).pdf` | past_paper | Primary OU corpus (17 pp) |
| `OU QUESTION PAPERS.pdf` | past_paper | Likely duplicate of above |
| `PPL previous papers.pdf` | past_paper | **Wrong course** — PPL fixture, not chemistry |
| `engineering chemistry updated.pdf` | notes | Study notes |
| `chemistry syllabus.pdf` | notes | Syllabus (should be `syllabus` kind for best mapping) |

Recommend removing **PPL previous papers.pdf** from the chemistry course to avoid mixed analytics.

## Parser reference — OU PDF only (`OU QUESTION PAPERS (1).pdf`)

| Metric | Value |
|--------|-------|
| PDF pages | 17 |
| Parsed questions (regex parser) | **119** |
| Distinct `paper_label` values | **5** (not 13) |

### Paper label breakdown (parser)

| paper_label | Questions |
|-------------|-----------|
| March 2023 | 58 |
| October 2023 | 25 |
| April 2022 | 18 |
| *(null / undetected)* | 17 |
| July 2021 | 1 |

**Why UI shows "4 papers" not 13:** Analytics counts **distinct non-null `paper_label` values** (4), not the number of bundled exam booklets in the PDF. The OU PDF merges many sessions; only **date headers** the regex recognizes become labels. Expanding to 13 requires **chemistry-specific parser rules** (future slice).

## Post-derive analytics baseline (DB course `chemistry`)

| Metric | Value |
|--------|-------|
| question_count | 119 |
| concept_count | 230 |
| classified_concept_count | 229 |
| unclassified_only_questions | 0 |
| unclassified_pct | 0.0% |
| total_marks | 119 (null marks → 1 each) |
| distinct_papers | 4 |
| tier | 1 (`structure_mode=organized`, no mapped `course_units` tree) |

### Top concepts by marks weightage (compare in UI)

| Rank | Label | weightage_pct | unique_q | paper_reach |
|------|-------|---------------|----------|-------------|
| 1 | How composites classified | 2.68% | 8 | 3 |
| 2 | Applications How Functionality | 2.32% | 4 | 2 |
| 9 | condesation polymerisation example | 1.69% | 3 | 1 |
| 10 | Calculate total hardness | 1.68% | 6 | 2 |
| 11 | preparation properties applications | 1.65% | 7 | 3 |
| 12 | Trans-esterification PART-B | 1.56% | 4 | 2 |
| 13 | electrolytic galvanic cells | 1.50% | 4 | 2 |
| 14 | Octane number Cetane | 1.44% | 5 | 3 |
| 15 | How | 1.30% | 7 | 1 |

Regenerate full JSON:

```powershell
cd C:\Projects\studypilot-v2\apps\api
$env:STUDYPILOT_AUTH_DISABLED='1'
python -m app.cli.exam_analytics --course chemistry
```

## Syllabus mapping — period split fix

Syllabus subtopics were only split on **commas**, not **periods** (e.g. `Water Chemistry. Corrosion. Corrosion control methods` stayed as one node).

**Fixed (2026-07-03):** `_split_comma_separated_topics` in `pdf_extract.py` and pasted structure import now split on **`,` and `.`** (with decimal/abbreviation guards).

**Re-import syllabus** after fix: Course structure → import syllabus → preview should show separate subtopics per period.

## UI checklist (manual)

- [ ] Exam Analytics shows **229** classified concepts (not 0)
- [ ] Top concept includes composites / materials cluster
- [ ] Re-import syllabus → period-separated subtopics in preview
- [ ] Tier 3 tree appears only after promote to **mapped** + confirm structure
- [ ] Answer-on-tap works when notes uploaded (tier 2+)

## Commands (repro)

```powershell
# Postgres + API + web (separate terminals)
cd C:\Projects\studypilot-v2
docker compose up -d postgres
$env:STUDYPILOT_AUTH_DISABLED='1'
.\scripts\start_api.ps1

cd C:\Projects\studypilot-v2\apps\web
npm run dev
# → http://127.0.0.1:5175

# Backfill concepts (if needed again)
cd C:\Projects\studypilot-v2\apps\api
python -m app.cli.derive_exam_concepts --course chemistry
python -m app.cli.exam_analytics --course chemistry
```
