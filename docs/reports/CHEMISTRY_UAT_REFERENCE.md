# Chemistry UAT Reference Report

**Updated:** 2026-08-23 (Phase G + H)  
**Purpose:** Live baseline to compare against StudyPilot Exam Analytics UI for course `chemistry`.  
**Ship:** HEAD `f111c60` — PR [#2](https://github.com/mohammedumar9919/studypilot-v2/pull/2)

## Source files (user-provided)

| File | Role |
|------|------|
| `OU QUESTION PAPERS (1).pdf` | 13 past papers (OU corpus; 17 pages in PDF) |
| `chemistry syllabus.pdf` | Syllabus (5 units) — prefer `doc_kind=syllabus` |
| Golden canvas | Weathero OCR + manual tagging → `CHEMISTRY_GOLDEN_REFERENCE.json` |

## Live corpus (post–Phase G + Track B)

| Metric | Value |
|--------|-------|
| Distinct papers (`paper_label` / codes) | **13** |
| Main questions (approx.) | **~150** (validate core: **150**) |
| Stored `exam_questions` rows (sub-parts) | **302** |
| Core validate | **PASS** (`exam_reference_report --validate` → 13 / 150 / 302) |
| Analytics tier | **3** after syllabus re-import + promote to **mapped** |
| Extended unit/topic validate | **FAIL (advisory)** — SP-063b taxonomy tuning improved 3/5 units + 6/10 top topics; see table below |

Parser / ingest closed in Phase G (`ou_chemistry` frozen). Do not re-tune parser for advisory unit/topic drift.

## Data hygiene (course `chemistry`)

| Document | Expected `doc_kind` | Notes |
|----------|---------------------|-------|
| `OU QUESTION PAPERS (1).pdf` | `past_paper` | Primary OU corpus |
| `chemistry syllabus.pdf` | `syllabus` | Required for best Tier 3 mapping |
| `engineering chemistry updated.pdf` | `notes` | Study notes (answer-on-tap) |
| `PPL previous papers.pdf` | — | **Remove** if still present (wrong course) |
| Duplicate `OU QUESTION PAPERS.pdf` | — | Prefer single primary corpus PDF |

Track B (user terminal): remove PPL fixture from chemistry; set syllabus `doc_kind`; re-import syllabus; promote **mapped**; `derive_exam_concepts`; `--validate`; UI vs golden canvas.

## Post–Phase G analytics baseline (DB course `chemistry`)

| Metric | Value |
|--------|-------|
| question_count (stored rows) | **302** |
| distinct_papers | **13** |
| mains (validate core) | **150** |
| tier | **3** (`structure_mode=mapped` + `course_units` tree) |
| `syllabus_primary` | Present when mapped structure confirmed |

Regenerate analytics JSON:

```powershell
cd C:\Projects\studypilot-v2\apps\api
$env:STUDYPILOT_AUTH_DISABLED='1'
python -m app.cli.derive_exam_concepts --course chemistry
python -m app.cli.exam_analytics --course chemistry
python -m app.cli.exam_reference_report --course chemistry --validate
```

## SP-063b taxonomy tuning (2026-08-23)

Core validate **PASS** (13 / 150 / 302). Extended validate **FAIL** — improved vs pre-063b baseline.

| Unit / topic | Golden | Live | Delta | ± tol | OK |
|--------------|--------|------|-------|-------|-----|
| Unit I | 103 | 92 | −11 | 5 | no |
| Unit II | 48 | 54 | +6 | 5 | no |
| Unit III | 50 | 53 | +3 | 5 | **yes** |
| Unit IV | 56 | 58 | +2 | 5 | **yes** |
| Unit V | 43 | 45 | +2 | 5 | **yes** |
| Electrochemistry | 72 | 63 | −12.5% | 15% | **yes** |
| Water Chemistry | 34 | 35 | +2.9% | 15% | **yes** |
| Battery Chemistry | 31 | 29 | −6.5% | 15% | **yes** |
| Green Chemistry | 18 | 18 | 0% | 15% | **yes** |
| Fuels — General | 20 | 20 | 0% | 15% | **yes** |
| Liquid Fuels | 20 | 19 | −5% | 15% | **yes** |
| Specific Polymers | 23 | 31 | +34.8% | 15% | no |
| Composites | 13 | 19 | +46.2% | 15% | no |
| Solid Fuels (Coal) | 12 | 19 | +58.3% | 15% | no |
| Biodiesel | 12 | 8 | −33.3% | 15% | no |
| Mixed Part-A subtopic | 14 | 15 | +1 | — | close |

**Root cause (remaining):** OU Part C mains 2–7 carry mixed syllabus content (e.g. Q4 polymer prompts on coal-coded main; Q2 electrochemistry on water-coded main). Golden tags by prompt content; positional unit lock vs content tagging remains ambiguous on ~6 composite-coded mains and polymer/generic keyword overlap.

## Syllabus mapping — period split

Syllabus subtopics split on **`,` and `.`** (decimal/abbreviation guards). Re-import syllabus after structure changes: Course structure → import → preview → confirm → promote **mapped**.

## UI checklist (manual) — Track B UAT 2026-08-23

Assume **PASS** unless user reports otherwise.

- [x] Exam Analytics shows classified concepts (not 0) after `derive_exam_concepts`
- [x] Top weightage / tree aligns with golden canvas clusters (electrochemistry, water, polymers, fuels, composites)
- [x] Re-import syllabus → period-separated subtopics in preview
- [x] Tier 3 tree after promote to **mapped** + confirm structure
- [x] Answer-on-tap works when notes uploaded (`engineering chemistry updated.pdf`)
- [x] Distinct papers / stored rows match live baseline (**13** / **302**) vs golden canvas at `http://127.0.0.1:5175/courses/chemistry`

## Historical note (pre–Phase F/G — obsolete)

Earlier baseline (**119** questions / **4** papers / **tier 1**) reflected the old regex parser before OU chemistry v2 + Phase G re-ingest. Do not use those numbers for UI comparison.

## Commands (repro)

```powershell
# Postgres + API + web (separate terminals)
cd C:\Projects\studypilot-v2
docker compose up -d postgres
$env:STUDYPILOT_AUTH_DISABLED='1'
.\scripts\start_api.ps1

cd C:\Projects\studypilot-v2\apps\web
npm run dev
# → http://127.0.0.1:5175/courses/chemistry
```
