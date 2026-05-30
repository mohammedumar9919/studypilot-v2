---
name: council-merge-slice
description: Stage 3 — Lead chairman synthesis, gate run, CURRENT_STATE update after council review.
---

# Council Stage 3 — Synthesize

## Steps

1. Pick winning proposal from Stage 2 (or combine if non-overlapping).
2. User runs acceptance in **their terminal**:
   - `pytest` scoped tests
   - `.\scripts\run_phase1b_eval_fast.ps1` if retrieval touched
   - `.\scripts\phase_gate.ps1 -Phase <n>` when applicable
3. Update `docs/CURRENT_STATE.md` with metrics and next task.
4. Human Gate 2 — user approves merge.

## Do not merge if

- Stage 2 Block unresolved
- Eval precision below 100% or OOC below 10/10 after retrieval change
