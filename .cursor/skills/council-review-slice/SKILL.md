---
name: council-review-slice
description: Stage 2 — Review worker proposals against failures-checklist and eval impact. Approve, Concern, or Block before merge.
---

# Council Stage 2 — Review

## Mandatory for

- `retrieve.py`, `rerank.py`, `gate.py`
- `golden_set.jsonl`, Alembic, `models.py`, `api-contracts.md`
- `min_rerank_score` changes

## Checklist

1. `docs/failures-checklist.md` — any anti-pattern reintroduced?
2. Ownership — single agent per file?
3. Eval impact — will precision@5 or OOC regress?
4. If retrieval changed: user must run `run_phase1b_eval_fast.ps1` before merge.

## Vote

- **Approve** — proceed to Stage 3
- **Concern** — merge with documented follow-up
- **Block** — fix before merge

## Personas

Review as Agent C (retrieval), Agent B (ingest), Security (no secrets in repo). See `config/council/studypilot-board.yaml`.
