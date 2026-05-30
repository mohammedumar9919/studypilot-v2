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

**Immediate goal:** Wave 4a visual design pass (SP-035). SP-003 GitHub retrieval gate **DONE** (Git LFS + job executes). See [WORKER_TASK_CARDS_QUEUE.md](WORKER_TASK_CARDS_QUEUE.md).

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
| Full retrieval gate in GitHub CI | **DONE** — PPL PDFs via Git LFS; `retrieval-gate` runs ingest + eval (not skipped) |

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

## What's NEXT (locked sequence — Option A)

| # | Wave | Owner | Task |
|---|------|-------|------|
| 1 | **4a** | Lead + you → Agent E | Visual design pass (SP-035) — **before upload** |
| 2 | **4b** | Agent D + E | Upload API (SP-017), onboarding (SP-031); auth (SP-012) later |

**Styling:** Short Lead session to lock aesthetic → Agent E implements tokens in `apps/web`. See [WORKER_TASK_CARDS_QUEUE.md](WORKER_TASK_CARDS_QUEUE.md) Wave 4a placeholder.

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
