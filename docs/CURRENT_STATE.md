# StudyPilot v2 — Current State

**Last updated:** 2026-05-31  
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
| Mobile responsive audit (SP-033) | **DONE** (Agent E Wave 5 — 390px PASS) |

**Status:** **Pilot-ready** (Waves 0–5). **NEXT (optional):** SP-032 cram presets or campus pilot prep. Repo: `github.com/mohammedumar9919/studypilot-v2`.

---

## Accuracy baseline

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
| Tesseract OCR + `scripts/ingest_ppl_pyq.ps1` | **DONE** |
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

## What's NEXT

| # | Priority | Item | Owner |
|---|----------|------|-------|
| 1 | Optional | SP-032 cram presets (summary, flashcards) | Agent D + E |
| 2 | Optional | SP-015 exam preset / review modes | D + E |
| 3 | Pilot | Campus demo — upload → ask → cite → heatmap | You |
| 4 | Defer | SP-012 auth, SP-013 async ingest, SP-014 observability | Phase 5+ |

---

## Environment

| Item | Value |
|------|-------|
| Postgres | `localhost:5433` |
| API dev | `localhost:8001` |
| Web dev | `localhost:5173` (Vite proxy → API) |
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
