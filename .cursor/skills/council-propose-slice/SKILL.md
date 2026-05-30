---
name: council-propose-slice
description: Stage 1 — Lead writes task card and spawns parallel worker proposals for a StudyPilot slice. Use when starting Agent B/C/D/E work.
---

# Council Stage 1 — Propose

## When to use

Starting a non-trivial slice (retrieval, ingest, API, web feature).

## Steps

1. Read `docs/CURRENT_STATE.md` and `docs/GAP_BACKLOG.md`.
2. Assign **one owner** (B/C/D/E) per file from `AGENTS.md`.
3. Write task card with:
   - Allowed paths
   - Forbidden paths
   - Acceptance command (pytest scope or eval script)
4. User opens **new worker chat** per agent if parallel Stage 1 needed (max 2–3).
5. Collect each worker's: summary, files changed, risks for Stage 2.

## Output

Task card ready for Gate 1 (user approval) before coding.
