# Agent D — Task Card: Outline API (Wave 2 — after Agent E)

**Copy below into a new Cursor chat when Wave 1 heatmap is merged.**

> **Wave 1 complete (2026-05-30).** Agent E shipped heatmap + student UX. Proceed with outline API.

---

You are **Agent D** for StudyPilot v2 — **API only**.

## Read first

- `docs/CURRENT_STATE.md`, `docs/GAP_BACKLOG.md` (SP-010)
- `docs/api-contracts.md` — add new route with version note
- `eval/fixtures/ppl/ppl_outline.yaml`

## Own ONLY

- `apps/api/app/main.py` (new route)
- `apps/api/app/services/` — new small module e.g. `course_outline.py` OR extend existing outline loader
- `apps/api/tests/test_course_outline.py`

## FORBIDDEN

- `apps/web/**` (Agent E consumes API)
- `retrieve.py`, `ingestion.py` unless orchestrator approves

## Deliverable

`GET /api/v1/courses/{course_id}/outline`

Response: units with id, title, page ranges, sections (from `ppl_outline.yaml` for PPL v1).

404 if unknown course. No LLM.

## Acceptance

- pytest new test passes
- `curl http://localhost:8001/api/v1/courses/PPL/outline` returns 5 units
- Document in `api-contracts.md`

## Handoff to Agent E

Paste response JSON shape for TOC sidebar task.

---

# Agent E — Task Card: Course TOC Sidebar (Wave 2 — after outline API)

**Copy below after Agent D ships outline endpoint.**

> **Wave 2 complete (2026-05-30).** Agent D outline API + Agent E `CourseOutlineSidebar`. Wave 3 next.

---

You are **Agent E** — **web only**.

## Read first

- `docs/AGENT_E_TASK_CARD_3C-C.md` (same ownership rules)
- New outline API contract in `api-contracts.md`

## Deliverable

- Sidebar tree: Unit → Section from **outline API** (not `retrieval_debug.chunks`)
- Works **before** any query is run
- Click section → prefill question textarea with section title
- MedX “browse before search” pattern (GAP B1)

## Own ONLY

- `apps/web/**`

## Acceptance

- Open app, select PPL, see full 5-unit tree without submitting a query
- Click “Unit 2 > Expressions…” → question prefilled

---

# Agent C / B — no active task

Retrieval at **100%**. PYQ OCR done. Do not assign unless regression or new course ingest.

---

## Wave 3 — COMPLETE (2026-05-31)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | `POST /api/v1/query/stream` (SSE) | pytest 13/13 |
| E | Stream UI + fallback | `npm run build` PASS |

Archived cards: Wave 3 Agent D/E sections in git history. Contract: [api-contracts.md](api-contracts.md).

---

## Wave 3.5 — COMPLETE (2026-05-31)

| Deliverable | Verification |
|-------------|--------------|
| Git LFS for PPL PDFs | Fresh clone → real PDFs (not pointers) |
| `retrieval-gate` in CI | Executes (skip step not run); [PR #1](https://github.com/mohammedumar9919/studypilot-v2/pull/1) |
| `api-and-web` | pytest 56/56 PASS |

Repo: `https://github.com/mohammedumar9919/studypilot-v2.git` — merge PR #1 to land on `main`.

---

## Wave 4a — COMPLETE (2026-05-31)

| Deliverable | Verification |
|-------------|--------------|
| Design tokens (`tokens.css`, `wave4a-theme.css`) | Warm dark-charcoal + teal system |
| Premium motion (CSS-only) | Ambient streaks, journey strip, slide-in sources, bar-grow heatmap |
| `StudyJourneyStrip` + stage pill | Synced to SSE stages |
| Behavior preserved | Stream, fallback, debug, heatmap, outline |
| Build | `npm run build` PASS |

---

## Wave 4b — COMPLETE (2026-05-31)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | `POST .../documents` upload API | pytest 10/10 |
| E | Upload UI + empty states (SP-031) | `npm run build` PASS |

Key files: `uploadClient.ts`, `DocumentUploadPanel.tsx`, `EmptyCourseState.tsx`, journey strip Upload/Index sync, outline+heatmap `refreshToken`.

---

## Wave 5 — COMPLETE (2026-05-31)

| Deliverable | Verification |
|-------------|--------------|
| SP-033 mobile audit @ 390px | All student flows PASS |
| Touch/gutter/layout tokens | `tokens.css` |
| Overflow guards + 5-col journey grid | `App.css`, `wave4a-theme.css` |
| Build | `npm run build` PASS |

Known limits: 320px labels tight; debug panels dense (student mode hides).

---

## Wave 5.5 — COMPLETE (2026-05-31)

Course name on upload panel; Studying pill in student mode; `setCourseId` on upload success.

---

## Wave 6 — COMPLETE (2026-05-28)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | Preset routing `study` \| `summary` \| `flashcards` on `/query` + `/query/stream` | pytest 29/29 |
| E | Pill tabs, `queryPresets.ts`, journey Review focus, preset in request body | `npm run build` PASS |

Key files: `generate.py`, `queryPresets.ts`, `QueryForm.tsx`, `useStudyQuery.ts`, `StudyJourneyStrip.tsx`, `App.tsx`.

---

## Wave 6.5 — Generic outline + PYQ heatmap (NEXT — Agent D then E, SP-036)

> **Symptom:** Chemistry (and other non-PPL courses) — query works; outline sidebar + exam heatmap empty. Root cause: `_OUTLINE_PATHS` and `_SEED_PATHS` are PPL-only in `course_outline.py` and `topic_frequency.py`.

### Agent D — paste first

---

You are **Agent D** for StudyPilot v2 — **API only** (Wave 6.5, SP-036).

## Skill invocation

- **using-superpowers** → **TDD** → **verification-before-completion**
- Council Stage 2 if updating `api-contracts.md`
- Do **not** change retrieve/rerank/gate; no `quick_gate.ps1` unless retrieval touched

## Read first

- `docs/CURRENT_STATE.md` — Chemistry gap note
- `apps/api/app/services/course_outline.py` — PPL-only `_OUTLINE_PATHS`
- `apps/api/app/services/exam/topic_frequency.py` — PPL-only outline + seed
- `eval/fixtures/ppl/ppl_outline.yaml` — target JSON shape
- `apps/api/app/services/pdf_extract.py` — `DocumentOutline`, `load_outline`
- `docs/api-contracts.md` — outline + topic-frequency routes

## Own ONLY

- `apps/api/app/services/course_outline.py`
- `apps/api/app/services/exam/topic_frequency.py`
- Optional: `apps/api/app/services/ingestion.py` (outline on ingest) or new outline upload route
- `apps/api/app/main.py` (if new route)
- `apps/api/tests/` — new/extended tests
- `docs/api-contracts.md`

## FORBIDDEN

- `apps/web/**` (Agent E after D)
- `retrieve.py`, `rerank.py`, gate changes

## Deliverable

Make `GET /api/v1/courses/{id}/outline` and `GET /api/v1/courses/{id}/exam/topic-frequency` work for **any** course with ingested notes + past papers.

### Outline resolution order (per course_id)

1. PPL fixture YAML — **unchanged** (`eval/fixtures/ppl/ppl_outline.yaml`)
2. DB-stored outline (new: JSON column on `Course` or `CourseOutline` table)
3. Auto-stub from notes document: unit per notes PDF, sections from page ranges (e.g. every N pages)

### Topic frequency for generic courses

1. If seed YAML exists → existing PPL path
2. Else: count `past_paper` chunks by page → map to outline section via page ranges; fallback unit = document filename or `"General"`

### Optional (v1 nice-to-have)

`POST /api/v1/courses/{id}/outline` — upload YAML matching `DocumentOutline` shape

## Acceptance

- pytest: Chemistry-like course (notes + past_paper chunks) → outline non-empty, topic-frequency non-empty
- PPL behavior unchanged (existing tests pass)
- Manual: re-test Chemistry — sidebar TOC + heatmap populate
- Document any new routes/shapes in `api-contracts.md`

## Handoff to Agent E

Response JSON shapes + stub vs full outline indicator (if added) for empty-state UX.

---

### Agent E — after Agent D (Wave 6.5b)

---

You are **Agent E** — **web UI** (Wave 6.5b, SP-036).

## Deliverables

1. Helpful empty/stub copy when outline is auto-generated (e.g. "Upload outline YAML for finer sections" if upload exists)
2. Heatmap renders generic units without PPL-specific labels
3. `npm run build` PASS; 390px OK

**Forbidden:** `apps/api/**`

---

## After Wave 6.5 — optional waves

**Shipped (Waves 0–6):** retrieval @ 100%, CI+LFS, SSE streaming, premium UI, upload+onboarding, mobile @ 390px, cram presets.

| ID | Item | When |
|----|------|------|
| SP-036 | Generic outline + PYQ heatmap | Wave 6.5 — **active** |
| SP-015 | Exam preset / review mode | After 6.5 |
| SP-012 | Auth + multi-page UI | Phase 5 |
| SP-020 | docker-compose full profile | Ops |

**Agents B/C:** idle. **Next:** SP-012 (Phase B) or Wave 8 (optional).

---

## SP-015 — COMPLETE (2026-05-28)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | `preset: exam`, past_paper retrieval, PYQ prompt | pytest 26/26, quick_gate -Smoke |
| E | Fourth pill, Exam journey, empty states | `npm run build` PASS |

**6-step journey:** DONE. Presets: study | summary | flashcards | exam.

---

## Wave 7 — COMPLETE (2026-05-28)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | Heading extract, normalize, outline_quality, outline_hints + retrieve wiring | pytest 51/51 serial, quick_gate -Smoke |
| E | Quality badges, OutlineConfirmPanel, low recovery CTAs | `npm run build` PASS |

---

## Wave 8 — LLM outline improve (optional — SP-041)

POST /outline/improve + accept; "Improve outline with AI" button when quality=low.

---

## Wave 7 — archived (summary)

Heading fallback, outline_quality score, dynamic retrieval hints from stored outline, confirm UI on upload.

---

## Wave 6.6 — COMPLETE (archived summary)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | Generic outline + topic-frequency API | pytest 23/23 |
| E | Stub notice, empty heatmap, generic labels | `npm run build` PASS |

**Limitation:** auto_stub = 10-page buckets; heatmap maps PYQ pages to those buckets. Wave 6.6 fixes.

---

## Wave 6.6 — Real TOC + keyword heatmap (NEXT — Agent D then E, SP-037)

> **Symptom:** Chemistry shows "pages 1–10", "pages 11–20" — not real topics. Exam heatmap counts pages, not chemistry topics.

### Agent D — paste first

See full card in chat handoff (Lead orchestrator) or below in queue update.

### Agent E — after Agent D (Wave 6.6b)

UI: `outline_source: extracted` banner, uploaded banner, optional outline upload button.

---

## Wave 5 — archived

Mobile audit card in git history.

## Wave 4b — archived

Agent D + E cards in git history. Contract: [api-contracts.md](api-contracts.md).

## Wave 4a — archived

Design brief: [DESIGN_DIRECTION_WAVE4A.md](DESIGN_DIRECTION_WAVE4A.md). Agent E card in git history.
