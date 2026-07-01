# StudyPilot v2 — Current State

**Last updated:** 2026-07-01  
**Status owner:** Lead orchestrator (update this file after every phase gate or major eval run)

This is the **single source of truth** for execution status. A new Cursor chat should read this first, then [LEAD_ORCHESTRATOR.md](LEAD_ORCHESTRATOR.md) and [COUNCIL_ORCHESTRATION.md](COUNCIL_ORCHESTRATION.md).

---

## Executive summary

| Area | Status |
|------|--------|
| Phases 0–2 + gates | **DONE** |
| Phase 3B — outline ingest + metadata retrieval + TOC UI (query chunks) | **DONE** |
| Phase 3C-A — PYQ OCR ingest | **DONE** (26/30 readable pages) |
| Phase 3C-B — topic frequency API + CLI | **DONE** |
| Phase 3C-C — exam heatmap UI (Agent E) | **DONE** |
| Retrieval accuracy | **100%** precision@5 (40/40), OOC **10/10** |
| Course TOC browse (pre-query) | **DONE** (Agent D API + Agent E sidebar) |
| Query streaming UX (SSE) | **DONE** (Agent D API + Agent E UI, Wave 3) |
| Visual design / motion (SP-035) | **DONE** (Agent E Wave 4a — tokens + NTR-inspired motion) |
| In-app PDF upload (SP-017) | **DONE** (Agent D API + Agent E UI, Wave 4b) |
| Onboarding / empty states (SP-031) | **DONE** (Agent E Wave 4b) |
| Mobile responsive audit (SP-033) | **DONE** (Agent E Wave 5) |
| Course name before upload (Wave 5.5) | **DONE** — upload panel + Studying pill |
| Cram presets (SP-032) | **DONE** — study / summary / flashcards (Wave 6 D+E) |
| Generic outline + heatmap (SP-036) | **DONE** | Wave 6.5 |
| Real TOC extraction + keyword heatmap (SP-037) | **DONE** | Wave 6.6 |
| Chapter-level outline rollup (SP-038) | **DONE** | Wave 6.7 |
| Universal outline pipeline (SP-039) | **DONE** | Wave 7 |
| Exam preset (SP-015) | **DONE** | `exam` preset — past_paper retrieval + PYQ answers |
| Phase A.5 — Exam Truth (Wave 9) | **DONE** | `exam_questions` + parsed heatmap + exam retrieval |
| SP-015.2 exam/status + exam gate | **DONE** | `exam_index_ready`, `min_rerank_score_exam=0.25` |
| SP-043 PPL OCR re-ingest | **DONE** | 29/30 readable; OCR `<=` threshold fix |
| SP-044 Chemistry syllabus merge | **DONE** | TOC page-number merge |
| SP-044.1 Chemistry UNIT X.Y rollup | **DONE** | Body anchors; user UAT PASS |
| SP-042a exam_questions + parser | **DONE** | 25/25 page-3 parity; re-ingest populates DB |
| SP-042b exam question retrieval | **DONE** | BM25+vector on prompts → chunk citations |
| SP-042a.1 web parsed banner | **DONE** | `heatmap_source: parsed` in UI |
| SP-050a Quick Study layout (Phase S) | **DONE** | `GET .../study-layout`; corpus SourcesPanel; PPL mapped unchanged |
| SP-050b Source-scoped retrieval (Phase S) | **DONE** | `GET .../documents` + optional `source_ids`; SourcesPanel checkboxes; smoke PASS |
| SP-050c Upload intent (Phase S) | **DONE** | `upload_intent` field; quick skips outline extract; pytest 31/31; build PASS |
| SP-051a study_topics + structure_mode (Phase S) | **DONE** | Alembic 004; CRUD API; layout `structure_mode`; pytest 18/18 |
| SP-051b Organized Study + topic_ids (Phase S) | **DONE** | TopicsPanel; structure-mode promote; pytest 34/34; build PASS |
| SP-052 Course Map promotion gate (Phase S) | **DONE** | Eligibility + promote API + UI tabs; pytest 19/19; UAT PASS (PPL) |
| SP-052.1 Syllabus-driven promote outline (Phase S) | **DONE** | `build_outline_for_promotion` on promote + rebuild-outline API |
| SP-053a Course structure schema + import (Phase S) | **DONE** | Alembic 005; paste/syllabus preview/confirm |
| SP-053a.1 Hierarchical parser + parts (Phase S) | **DONE** | Alembic 006; CN live-shape fixture; comma-aware topics |
| SP-053a.1b Parser hotfix (Phase S) | **DONE** | Line-wrap merge, colon/bold parts, Roman title repair |
| SP-053b Structure M2M + query scope (Phase S) | **DONE** | `unit_ids`/`part_ids`/`subtopic_ids`; pytest 44/44; commit `0fa34c1` |
| SP-053c Unified Course structure UI (Phase S) | **DONE** | Sources \| Course structure tabs; Agent E; user UAT PASS |
| SP-060a exam concept extraction (Phase E) | **DONE** | Alembic 009; YAKE extract + FastEmbed merge; ingest hook; pytest 16/16 |
| SP-060c exam analytics structure mapping (Phase E) | **DONE** | Tier 3 rollup on `GET .../exam/analytics`; pytest 6/6; api-contracts 1.11.0 |

**Status:** **Phase B — fully closed** (012a–d + **012.5 polish**). **Phase C — Platform slices DONE** (013a–c, 045a/b, 004a). **Phase E — SP-060a/060b/060c DONE**. **NEXT: SP-060d** (answer-on-tap). **DEFERRED:** SP-014 observability, exam golden set, SP-041, SP-060e–060f.

**Gate remediation (2026-06-19):** Full `quick_gate` FAIL was env/data, not a code regression. Root cause of OOC 8/10: `engineering chemistry updated.pdf` was wrongly ingested under `course_id=PPL`, so `ppl-ooc-04`/`ppl-ooc-06` retrieved chemistry pages instead of refusing. Fixed by pruning the mis-ingested doc from PPL (`apps/api/scripts/cleanup_ppl_corpus.py`); the `chemistry` course keeps its copy. pytest "too many clients"/deadlock was eval+pytest connection overlap. **Post-fix: OOC 10/10, 0/40 in-corpus refused, pytest 346 passed.**

### Build order (product-first)

| Phase | Status | Next |
|-------|--------|------|
| **A — Study workspace** | **DONE** (presets, outline pipeline, exam mode) | — |
| **A.5 — Exam Truth** | **DONE** | — |
| **S — Flex Study** | **DONE** | — |
| **B — Full product shell** | **DONE** | 012a–012d + **012.5** polish complete |
| **C — Platform** | **DONE** (planned slices) | 013a–c, 045a/b, 004a complete; SP-014/041 deferred |
| **E — Exam intelligence** | **IN PROGRESS** | SP-060a/060b/060c **DONE**; **NEXT: SP-060d** answer-on-tap |

---

| Metric | Value |
|--------|-------|
| precision@5 | **100%** (40/40) @ `min_rerank_score=0.35` |
| OOC | **10/10** |
| Top misses | **None** |

Reports: `eval/reports/PHASE1B_SUMMARY_FOR_AGENT.txt`, `eval/reports/latest.jsonl`

**Maintain:** Re-run `run_phase1b_eval_fast.ps1` after any retrieval/rerank/gate change. Target CI gate @ 100% (Wave 3).

---

## Phase 3C — PYQ / exam intelligence

| Deliverable | Status |
|-------------|--------|
| `past_paper` ingest + study exclusion | **DONE** |
| Tesseract OCR + `scripts/ingest_ppl_pyq.ps1` | **DONE** (29/30 readable after SP-043) |
| `GET /api/v1/courses/{id}/exam/topic-frequency` | **DONE** |
| `eval/fixtures/ppl/ppl_pyq_seed.yaml` + keyword matcher | **DONE** (~50 est. questions) |
| Heatmap UI in `apps/web` | **DONE** |

---

## Phase 3 Wave 2 — Course outline (SP-010)

| Deliverable | Status |
|-------------|--------|
| `GET /api/v1/courses/{id}/outline` + `course_outline.py` | **DONE** (Agent D, pytest 6/6) |
| Pre-query TOC sidebar in `apps/web` | **DONE** (Agent E, `CourseOutlineSidebar`) |

---

## Phase 3 Wave 3 — CI gate + streaming (SP-003, SP-004)

| Deliverable | Status |
|-------------|--------|
| `.github/workflows/eval-gate.yml` | **DONE** — pytest + web build every PR |
| `eval/ci_gate.py` + `scripts/ci_eval_gate.sh` | **DONE** — 100% precision + OOC gate |
| `phase_gate.ps1 -Phase 3` | **DONE** — local 100% gate |
| Local Phase 3 gate (`quick_gate.ps1`) | **DONE** — 100% (40/40), OOC 10/10 (user verified) |
| `POST /api/v1/query/stream` (SSE) | **DONE** (Agent D, pytest 6/6 stream + query API 13/13) |
| Streaming UI + non-stream fallback | **DONE** (Agent E, `npm run build` PASS) |
| Full retrieval gate in GitHub CI | **DONE** — Git LFS (`eval/fixtures/ppl/*.pdf`); `retrieval-gate` runs (not skipped). Repo: `github.com/mohammedumar9919/studypilot-v2` |

---

## Phase 3 Wave 3.5 — Git LFS + cloud CI (SP-003)

| Deliverable | Status |
|-------------|--------|
| `.gitattributes` LFS track `eval/fixtures/ppl/*.pdf` | **DONE** |
| `eval-gate.yml` — `lfs: true`, postgres wait, BOM strip | **DONE** |
| Fresh clone + `git lfs pull` → real PDFs | **DONE** (verified) |
| `api-and-web` on PR #1 | **PASS** (pytest 56/56) |
| `retrieval-gate` executes ingest + eval | **DONE** (not skipped; confirm green after PR merge) |

**Stream contract:** `retrieval_complete` → `token` → `done` (refusal: `done` only). Documented in [api-contracts.md](api-contracts.md).

---

## Query latency

| Aspect | Status |
|--------|--------|
| Total E2E time | Still ~**60s** (LLM-bound) |
| Perceived UX | **Improved** — sources ~10–15s (`retrieval_complete`), answer tokens stream during generation |
| Student path | `debugEnabled: false` → `POST /api/v1/query/stream` |
| Phase 4 | GPU / faster model routing (optional) |

---

---

## Phase 4 Wave 4a — Visual design (SP-035)

| Deliverable | Status |
|-------------|--------|
| `tokens.css` + `wave4a-theme.css` design system | **DONE** |
| Warm dark-charcoal + teal accent, ambient streaks | **DONE** |
| `StudyJourneyStrip` (5 steps synced to SSE) | **DONE** |
| Glass panels, stage pill, sources slide-in, bar-grow heatmap | **DONE** |
| CSS-only motion + `prefers-reduced-motion` | **DONE** (no framer-motion) |
| `npm run build` | **PASS** |

Brief: [DESIGN_DIRECTION_WAVE4A.md](DESIGN_DIRECTION_WAVE4A.md)

---

## Phase 4 Wave 4b — Upload + onboarding (SP-017, SP-031)

| Deliverable | Status |
|-------------|--------|
| `POST /api/v1/courses/{course_id}/documents` | **DONE** (Agent D, pytest 10/10) |
| `document_upload.py` — sync multipart ingest | **DONE** |
| `uploadClient.ts` + `DocumentUploadPanel.tsx` | **DONE** |
| `EmptyCourseState.tsx` — SP-031 onboarding | **DONE** |
| Journey strip Upload/Index steps + outline/heatmap refresh | **DONE** |
| `npm run build` | **PASS** |

---

---

## Phase 5 — Mobile audit (SP-033)

| Deliverable | Status |
|-------------|--------|
| Full student journey @ **390px** | **PASS** (all flows) |
| Touch targets ≥44px, no main-column horizontal scroll | **DONE** |
| 900px column transition | **PASS** |
| Tokens: `--sp-touch-min`, `--sp-page-gutter`, `--sp-layout-split` | **DONE** |
| `npm run build` | **PASS** |

**Known limits:** 320px journey labels tight; debug panels dense (hidden in student mode).

---

## Phase 5 Wave 5.5 — Course setup UX

| Deliverable | Status |
|-------------|--------|
| Editable course name/code on upload panel | **DONE** |
| `setCourseId` on upload success | **DONE** |
| Student mode: Studying pill | **DONE** |
| `npm run build` | **PASS** |

---

## Phase 6 — Cram presets (SP-032)

| Deliverable | Status |
|-------------|--------|
| API preset routing (`study` \| `summary` \| `flashcards`) | **DONE** (Agent D, pytest 29/29) |
| `generate.py` preset prompts + stream path | **DONE** |
| `queryPresets.ts` + pill tabs in `QueryForm.tsx` | **DONE** (Agent E) |
| `useStudyQuery` passes `preset` (stream + fallback) | **DONE** |
| Journey strip Review focus for summary/flashcards | **DONE** |
| `npm run build` | **PASS** |

---

## Phase 7 — Universal outline pipeline (SP-039)

| Deliverable | Status |
|-------------|--------|
| Extract order: bookmarks → text TOC → **headings** → auto-stub | **DONE** |
| `normalize_outline()` + `outline_quality_score()` | **DONE** |
| `outline_quality` + `outline_granularity` on GET /outline | **DONE** |
| Dynamic retrieval hints (`outline_hints.py`, per-course) | **DONE** |
| Agent E: quality badges, confirm panel, low-quality recovery | **DONE** |
| pytest 51/51 serial + `quick_gate.ps1 -Smoke` PASS | **DONE** |
| `npm run build` | **PASS** |

**Note:** Run pytest outline/retrieval suites **serially** on `studypilot_test` to avoid Postgres deadlock flakes from parallel jobs.

---

| Deliverable | Status |
|-------------|--------|
| `normalize_outline_chapters()` in pdf_extract.py | **DONE** |
| `outline_granularity`: chapter \| section \| page_stub | **DONE** |
| Topic frequency unit rollup + `?detail=sections` | **DONE** |
| Agent E: PPL-like sidebar, chapter banner, unit heatmap | **DONE** |
| pytest 32/32 + `npm run build` PASS | **DONE** |

---

## Phase 6.6 — Real TOC + keyword heatmap (SP-037)

| Deliverable | Status |
|-------------|--------|
| Hybrid TOC extraction (bookmarks → text → stub) | **DONE** |
| `outline_source: extracted` + rebuild route | **DONE** |
| Keyword exam heatmap (no page cross-map) | **DONE** |
| Agent E: banners, upload/rebuild actions | **DONE** |
| pytest 28/28 + `npm run build` PASS | **DONE** |

**SP-044 / SP-044.1:** Engineering Chemistry sidebar fixed — body-confirmed major units (`UNIT N`), orphan subsection reassignment (3.x/4.x → unit 2), strict X.Y parsing (no math false positives). Re-extract TOC after API restart.

---

| Deliverable | Status |
|-------------|--------|
| `Course.outline_data` JSONB + migration | **DONE** |
| 3-tier outline: fixture → uploaded → auto_stub | **DONE** |
| `POST /api/v1/courses/{id}/outline` upload | **DONE** |
| Generic topic-frequency (page-mapped) | **DONE** (limitation — fixed in 6.6) |
| Agent E: stub notice, empty heatmap states | **DONE** |
| pytest 23/23 + `npm run build` PASS | **DONE** |

---

## Phase SP-015 — Exam preset

| Deliverable | Status |
|-------------|--------|
| `preset: exam` — `past_paper` retrieval only | **DONE** (Agent D) |
| Study presets exclude past_paper (unchanged) | **DONE** — quick_gate smoke 10/10 |
| `_EXAM_SYSTEM_PROMPT` + stream/non-stream | **DONE** |
| Fourth pill tab + journey Exam focus | **DONE** (Agent E) |
| Empty state (no past papers) | **DONE** |
| pytest 26/26 + `npm run build` PASS | **DONE** |

**Presets:** `study` | `summary` | `flashcards` | `exam`

---

## Phase A.5 — Exam Truth Layer (Wave 9)

| Deliverable | Status |
|-------------|--------|
| SP-015.1 course draft/commit + heatmap crash fix | **DONE** |
| SP-015.2 `GET .../exam/status`, `min_rerank_score_exam`, `refusal_reason` | **DONE** (pytest 23/23) |
| SP-015.2.1 PPL hints when `cid is None` | **DONE** — quick_gate -Smoke PASS |
| SP-015.2.2 ChunkInspector refusal-safe debug | **DONE** |
| SP-043 PPL PYQ OCR re-ingest | **DONE** — 29/30 readable |
| SP-044 Chemistry syllabus TOC merge | **DONE** |
| SP-044.1 Chemistry UNIT X.Y rollup + body anchors | **DONE** — pytest 15/15; user UAT PASS |
| SP-042a `exam_questions` schema + parser | **DONE** — migration 003; pytest 21/21 |
| SP-042b exam retrieval over question records | **DONE** — pytest 13/13; quick_gate -Smoke PASS |
| SP-042a.1 web types + parsed banner | **DONE** — `npm run build` PASS |
| `eval/exam_golden_set.jsonl` | **OPEN** (human approval; optional) |

**Council Stage 3:** Phase A.5 **closed** (2026-06-04). Study gate: `quick_gate.ps1 -Smoke` PASS (100% 10/10).

---

## Phase S — Flex Study (Wave 10+)

| Deliverable | Status |
|-------------|--------|
| SP-050a `GET .../study-layout` + corpus/mapped mode | **DONE** (Agent D, pytest 8/8) |
| SP-050a SourcesPanel + hide TOC/heatmap for corpus | **DONE** (Agent E, `npm run build` PASS) |
| Council Stage 3 smoke + UAT (050a) | **DONE** (2026-06-06) |
| SP-050b `GET /documents` + `source_ids` on query | **DONE** (Agent D+E, pytest 25/25; UAT PASS 2026-06-07) |
| SP-050c Upload intent metadata | **DONE** (Agent B+E, pytest 31/31; build PASS) |
| SP-051a `study_topics` + `structure_mode` | **DONE** (Agent D+B, Alembic 004, pytest 18/18) |
| SP-051b Organized Study UI + `topic_ids` query | **DONE** (Agent D+E, pytest 34/34; build PASS) |
| SP-052 Course Map promotion gate | **DONE** (Agent D+E, pytest 19/19; promote UI UAT) |
| SP-052.1 Syllabus-driven promote outline | **DONE** (promote + rebuild-outline; course_map tests) |
| SP-053a Course structure schema + import | **DONE** (Alembic 005; preview/confirm APIs) |
| SP-053a.1 Hierarchical parts + parser | **DONE** (Alembic 006; CN live-shape UAT PASS) |
| SP-053a.1b Parser hotfix | **DONE** (CN engineering syllabus UAT PASS) |
| SP-053b M2M assignments + structure query scope | **DONE** (pytest 44/44; smoke PASS) |
| SP-053c Unified Course structure UI | **DONE** (Agent E; CN + DS user UAT PASS) |
| SP-053d Modular syllabus depth | **DONE** (Data Science 5/5 units; CN regression 45 pytest) |

**Council Stage 3:** SP-012b **closed** (2026-06-02). User gate: `pytest tests/test_auth.py` 4/4; `quick_gate.ps1 -Smoke` **100% P@5 (10/10)**; commit `6a79564`.

---

## Phase B — Product shell (DONE)

| Deliverable | Status |
|-------------|--------|
| SP-012a Workspace schema (Alembic 007) | **DONE** | `users`/`workspaces`/`workspace_members`; `courses.workspace_id`; System Demo backfill; pytest 5/5; commit `c94ab42` |
| SP-012b Clerk JWT + dev bypass | **DONE** | Route guards on course/query/doc PATCH; bypass env; pytest 4/4; smoke 100%/10/10; commit `6a79564` |
| SP-012c Workspace course APIs | **DONE** | `GET/POST /api/v1/workspaces/me/courses`; upload auto-create; pytest 7/7; api-contracts **1.6.0** |
| SP-012d Multi-page shell | **DONE** | react-router + Clerk React; `/courses` dashboard; `authFetch` on all clients; `npm run build` PASS; user UAT PASS |
| SP-012.5 Phase B polish | **DONE** | Catch-all route → `/courses`; Vite dev port default **5175**; `.env.example` + Clerk prod docs; CoursesPage card-grid CSS; `npm run build` PASS |

**Council Stage 3:** SP-012.5 **closed** (2026-06-29). Agent E only; no backend/retrieval touch. UAT: `/foo` → `/courses` on `:5175`; courses create + list.

**Council Stage 3:** SP-012d **closed** (2026-06-02). User UAT: `http://127.0.0.1:5175/courses` → PPL study flow (port **5175** — Weathero occupies `:5173`).

**Human Gate 0:** Clerk auth; `STUDYPILOT_AUTH_DISABLED=1` for pytest/eval.

**Deferred:** exam golden set (human approval).

---

## Phase C — Platform (DONE)

| Slice | Status | Owner | Goal |
|-------|--------|-------|------|
| SP-013a | **DONE** | B + D | `ingest_jobs` schema (Alembic 008) + Postgres worker + enqueue; pytest **7/7**; smoke **100% P@5 (10/10)** |
| SP-013b | **DONE** | D | Async upload **202** + `GET .../ingest-status`; sync **201** fallback; api-contracts **1.8.0** |
| SP-013c | **DONE** | E | Web poll `ingest-status` + progress UI; `npm run build` PASS |
| SP-045a | **DONE** | B | PDF audit tier (`native`/`ocr`/`layout_defer`) in `extraction_quality` |
| SP-045b | **DONE** | B | Two-phase ingest: `fast` (native, no OCR) → `heavy` (OCR+PYQ); phase from `audit_tier` |
| SP-004a | **DONE** | D | `retrieval_debug.timings_ms`; optional `STUDYPILOT_RETRIEVAL_TIMEOUT_S`; pytest **5/5**; smoke **100% P@5 (10/10)** |

**Human Gate confirmed:** Phase C (not Phase E, not B polish).  
**Sequential rule:** 013a → 013b → 013c (no parallel 013b + 013c).  
**Product targets:** upload return &lt; 2s; progressive study-ready; honesty on `extraction_quality`.

**Deferred within Phase C:** SP-014 observability, SP-041 LLM outline, layout tier C (Docling/Marker).

**Council Stage 3 — SP-004a (closed 2026-06-17):** `pytest tests/test_query_latency_bounds.py` **5/5**; `quick_gate.ps1 -Smoke` **100% P@5 (10/10)**. No ranking/threshold changes.

**Council Stage 3 — Phase C ingest (closed 2026-06-17):**

| Slice | Gate |
|-------|------|
| SP-013b | Scoped pytest **43/43** ingest platform PASS; api-contracts **1.8.0** |
| SP-013c | `npm run build` PASS; optional UAT `:5175` upload poll PASS |
| SP-045a | `test_pdf_audit.py` + ingest e2e PASS |
| SP-045b | `test_ingest_two_phase.py` **10/10** PASS |

Retrieval untouched — no full eval for this closeout. Commit strategy: 3 logical commits on user request (`commit Phase C platform`).

**Council Stage 3 (prior):** SP-013a **closed** (2026-06-15). `pytest tests/test_ingest_queue.py` **7/7**; `quick_gate.ps1 -Smoke` **100% P@5 (10/10)**.

---

## Phase E — Exam intelligence (SP-060a / SP-060b / SP-060c)

| Deliverable | Status |
|-------------|--------|
| SP-060a Alembic 009 + concept derive engine | **DONE** |
| SP-060b `GET .../exam/analytics` + `analytics.py` | **DONE** |
| SP-060c Tier 3 structure mapping + `analytics_structure.py` | **DONE** |
| Auto-map concepts → syllabus nodes; unmapped list; rollup | **DONE** |
| `pytest test_exam_analytics_structure.py` | **6/6 PASS** |
| Full Phase E pytest (concept + analytics + structure) | **29/29 PASS** (1 skipped) |
| api-contracts **1.11.0** | **DONE** |

**Council Stage 3:** SP-060c closed (2026-07-01). No retrieval touch — `quick_gate` not required.

---

## What's NEXT

| # | Priority | Item | Owner |
|---|----------|------|-------|
| 1 | **ACTIVE** | **SP-060d** answer-on-tap (Tier 2/3 study RAG) | D + E |
| 2 | **DEFER** | SP-060e web Exam Analytics tab | E |
| 3 | **DEFER** | SP-060f predictions | — |
| 4 | **DEFER** | SP-014 observability / RAGAS | — |
| 5 | **DEFER** | Exam golden set (human approval) | — |

---

## Environment

| Item | Value |
|------|-------|
| Postgres | `localhost:5433` (StudyPilot; Zeref uses `5434` separately) |
| API dev | `localhost:8002` (`scripts/start_api.ps1`; orphan may block `:8001`) |
| Web dev | `localhost:5175` preferred (`npm run dev -- --port 5175`; Weathero may occupy `:5173`) |
| `rrf_output_top_k` | **24** |
| `min_rerank_score` | **0.35** |

### Re-eval (after retrieval changes)

**Full eval gate (~6–12 min, default):**

```powershell
cd C:\Projects\studypilot-v2
.\scripts\quick_gate.ps1
```

**Smoke only (~2–3 min):**

```powershell
.\scripts\quick_gate.ps1 -Smoke
```

---

## Key paths

| Path | Purpose |
|------|---------|
| `docs/GAP_BACKLOG.md` | Product gaps + MedX learnings (reconciled) |
| `docs/COUNCIL_ORCHESTRATION.md` | Karpathy 3-stage → StudyPilot governance |
| `config/council/studypilot-board.yaml` | Agent personas for council review |
| `eval/fixtures/ppl/ppl_outline.yaml` | Unit/section page map |
| `docs/CI_SETUP.md` | GitHub Actions + local 100% eval gate |
| `docs/ACCURACY_ROADMAP.md` | Milestone ladder |
