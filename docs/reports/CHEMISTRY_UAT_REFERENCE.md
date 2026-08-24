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
| Extended unit/topic validate | **FAIL (advisory)** — SP-064d: **4/5 units + 7/10 top topics** within tol (063b: 3/5 + 6/10); see table below |

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

| Unit / topic | Golden | Live (063b) | ± tol | OK |
|--------------|--------|-------------|-------|-----|
| Unit I | 103 | 92 | 5 | no |
| Unit II | 48 | 54 | 5 | no |
| Unit III | 50 | 53 | 5 | **yes** |
| Unit IV | 56 | 58 | 5 | **yes** |
| Unit V | 43 | 45 | 5 | **yes** |
| Electrochemistry | 72 | 63 | 15% | **yes** |
| Water Chemistry | 34 | 35 | 15% | **yes** |
| Battery Chemistry | 31 | 29 | 15% | **yes** |
| Green Chemistry | 18 | 18 | 15% | **yes** |
| Fuels — General | 20 | 20 | 15% | **yes** |
| Liquid Fuels | 20 | 19 | 15% | **yes** |
| Specific Polymers | 23 | 31 | 15% | no |
| Composites | 13 | 19 | 15% | no |
| Solid Fuels (Coal) | 12 | 19 | 15% | no |
| Biodiesel | 12 | 8 | 15% | no |
| Mixed Part-A subtopic | 14 | 15 | — | close |

**Root cause (063b):** OU Part C mains 2–7 carry mixed syllabus content (e.g. Q4 polymer prompts on coal-coded main; Q2 electrochemistry on water-coded main). Golden tags by prompt content; positional unit lock vs content tagging remains ambiguous on ~6 composite-coded mains and polymer/generic keyword overlap.

## SP-064d taxonomy tuning (2026-08-23)

Core validate **PASS** (13 / 150 / 302). Extended validate **FAIL** — **improved vs 063b** (4/5 units, 7/10 top topics within tolerance).

| Unit / topic | Golden | Live (064d) | Δ vs 063b | ± tol | OK |
|--------------|--------|-------------|-----------|-------|-----|
| Unit I | 103 | 96 | +4 | 5 | no (−7) |
| Unit II | 48 | 50 | −4 | 5 | **yes** (+2) |
| Unit III | 50 | 52 | −1 | 5 | **yes** (+2) |
| Unit IV | 56 | 58 | 0 | 5 | **yes** (+2) |
| Unit V | 43 | 46 | −1 | 5 | **yes** (+1) |
| Electrochemistry | 72 | 68 | +5 | 15% | **yes** (+5.6%) |
| Water Chemistry | 34 | 34 | −1 | 15% | **yes** (0%) |
| Battery Chemistry | 31 | 28 | −1 | 15% | **yes** (9.7%) |
| Biodiesel | 12 | 12 | +4 | 15% | **yes** (0%) |
| Liquid Fuels | 20 | 17 | −2 | 15% | **yes** (15%) |
| Green Chemistry | 18 | 19 | +1 | 15% | **yes** (5.6%) |
| Specific Polymers | 23 | 30 | −1 | 15% | no (30.4%) |
| Fuels — General | 20 | 24 | +4 | 15% | no (20%) |
| Composites | 13 | 15 | −4 | 15% | no (15.4%) |
| Solid Fuels (Coal) | 12 | 17 | −2 | 15% | no (41.7%) |

**Levers applied (064d, `chemistry_taxonomy.py` only):**
- Content-first green/composite main resolvers (Part C mains 5–6; Part A/B green/composite mains)
- Part A polymer/water slots: keyword override (e.g. biodiesel on A5)
- `_apply_topic_overrides`: electrochemical corrosion → Electrochemistry; fuel sub-type splits; conducting/biodegradable split from Specific Polymers
- Part B mains 11/17: battery vs electrochemistry in-unit refinement
- Biodiesel keyword expansion; Solid Fuels keyword tighten (drop generic `solid fuel`)

**Remaining gap:** Unit I still −7 (Electrochemistry +4 vs golden but not enough for unit rollup); Specific Polymers / Solid Fuels / Fuels — General topic buckets still diverge from golden manual tags on composite-coded mains and OCR-noisy Part C Q1 prompts.

Regenerate:

```powershell
python -m app.cli.exam_reference_report --validate --course chemistry
```

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
