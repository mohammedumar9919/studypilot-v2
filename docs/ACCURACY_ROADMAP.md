# Accuracy roadmap — StudyPilot v2

**Owner:** Lead orchestrator  
**Last updated:** 2026-05-30

Long-term goal: push retrieval **as close to 100% precision@5** as the corpus and golden set allow, without blocking MVP delivery on stretch targets.

**Related:** [CURRENT_STATE.md](CURRENT_STATE.md) · [eval/README.md](../eval/README.md) · [failures-checklist.md](failures-checklist.md)

---

## Milestones

| Milestone | precision@5 | OOC | Gate or stretch | Status |
|-----------|-------------|-----|-----------------|--------|
| **1c unlock** | ≥ 70% | 10/10 | **Hard gate** — blocks Phase 2 | **DONE** (2026-05-25) |
| **Stretch 1** | ≥ 80% | 10/10 | Soft — 32/40 hits | **DONE** (2026-05-27) |
| **Stretch 2** | ≥ 85% | 10/10 | Soft — product quality | **DONE** (2026-05-27) |
| **Stretch 3** | ≥ 90% | 10/10 | Soft — pre-hardening | **DONE** (100%) |
| **Pre-installer** | ≥ 95% | 10/10 | Human sign-off before Phase 5 | **DONE** (100%) |
| **CI lock** | 100% | 10/10 | PR gate — no regression | **OPEN** (Wave 3) |
| **Ceiling** | ~100% | 10/10 | Best effort; may need golden relabel | **DONE** (maintain) |

**Hard gate stays at 70%** in `phase_gate.ps1` until human ratchets CI (recommended: **100%** once Wave 3 Actions land).

---

## Current baseline (Phase 1c PASS)

| Item | Value |
|------|-------|
| `min_rerank_score` | **0.35** ([config.py](../apps/api/app/config.py)) |
| precision@5 | **100%** (40/40) |
| OOC refusal | **10/10** |
| Gate | `phase_gate.ps1 -Phase 1c` **PASS** |
| Top misses | **None** |

### Historical misses (resolved)

`ppl-002`, `ppl-013`, `ppl-022`, `ppl-035`, `ppl-052` — fixed via rerank-all-candidates + early-unit BM25 (Agent C, Phase 3B).

### Agent C fixes (2026-05-27)

Metadata-aware retrieval: threaded `unit`, `section_title`, `toc_path` through `RetrievedChunk`, added TOC/section BM25 stream fused via RRF, unit/section hinting from query phrases + outline-derived page ranges. Better page mapping in multi-page parents (anchor prioritization + range clamping). Rerank improvements (phrase/body boosts + stronger front-matter demotion) without changing `min_rerank_score`.

### Agent C fixes (2026-05-25)

Parent-aware page refinement, focus BM25 + third RRF stream, lexical hybrid weights, parent-aware rerank with score boost.

**Latency Tier 1 (same day):** `rrf_output_top_k` 30→24; rerank caps 2000/1500 chars. Gate still 70%/10-10. Do not use rrf=18 or child-only rerank.

---

## Eval discipline (always)

1. Use **`scripts/run_phase1b_eval_fast.ps1` only** — never the 4-threshold sweep.
2. Run Docker, ingest, eval, and gates in **user PowerShell** (not Cursor agent shell).
3. Set `$env:MIN_RERANK_SCORE` before eval **and** before `phase_gate.ps1 -Phase 1c` if overriding config.
4. Paste `eval/reports/PHASE1B_SUMMARY_FOR_AGENT.txt` into the lead chat after each run.
5. **Do not edit** `eval/golden_set.jsonl` without human approval.
6. Scoring: ±1 page tolerance per [score_precision.py](../eval/score_precision.py).

```powershell
cd C:\Projects\studypilot-v2
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
type eval\reports\PHASE1B_SUMMARY_FOR_AGENT.txt
.\scripts\phase_gate.ps1 -Phase 1c
```

---

## Phase-by-phase accuracy work

### Phase 2 — Chunk inspector (Agent E) — DONE

- UI at `apps/web/**` with debug panel + chunk inspector for 12 miss IDs
- **Target:** fix 2–3 misses per Agent C accuracy cycle → **80%**

### Phase 1 quality uplift (Agent C + optional Agent B)

| Lever | Owner | Expected gain |
|-------|-------|---------------|
| RRF weight + retrieval top-k tuning | Agent C | Broad/semantic misses |
| Contextual chunk prefixes (cheap LLM, once per doc) | Agent D | PYQ-style + late-unit |
| Chunk boundary / header stripping | Agent B | Early-page cluster |
| Stronger embed/rerank (if CPU budget) | Agent C | Diminishing returns |

**Target:** **85–90%** before Phase 4 hardening.

### Phase 4 — Regression protection

- CI golden-set gate: fail PR if precision drops below last recorded milestone.
- Log rerank scores + gate triggers per query.
- Optional RAGAS after retrieval ≥ 90%.
- Human golden-set audit for remaining misses.

**Target:** **95%+** on PPL golden set before Phase 5 campus installer.

---

## What we will not do

- Vector-only search; past_paper in Study mode; sanitizer ladder (see [failures-checklist.md](failures-checklist.md)).
- Block Phase 2 UI on stretch milestones.
- Raise the phase gate to 85% without explicit human decision.
