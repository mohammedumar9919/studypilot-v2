# Council skills — copy-paste into `.cursor/skills/`

Create each folder and `SKILL.md` under `C:\Projects\studypilot-v2\.cursor\skills\`.

Reference: [COUNCIL_ORCHESTRATION.md](COUNCIL_ORCHESTRATION.md) · [config/council/studypilot-board.yaml](../config/council/studypilot-board.yaml) (create YAML from [WAVE0_WAVE1_IMPLEMENTATION.md](WAVE0_WAVE1_IMPLEMENTATION.md))

---

## `council-propose-slice/SKILL.md`

```markdown
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
```

---

## `council-review-slice/SKILL.md`

```markdown
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

## Personas (optional prompts)

Review as Agent C (retrieval), Agent B (ingest), Security (no secrets in repo).
```

---

## `council-merge-slice/SKILL.md`

```markdown
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
- Eval precision &lt; 100% or OOC &lt; 10/10 after retrieval change
```

---

## `run-eval-gate/SKILL.md`

```markdown
---
name: run-eval-gate
description: User-terminal eval discipline for StudyPilot. Never use 4-sweep eval script.
---

# Run eval gate

## Commands (user PowerShell, repo root)

```powershell
cd C:\Projects\studypilot-v2
docker compose up -d

# Smoke
$env:GOLDEN_LIMIT = "10"
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
Remove-Item Env:GOLDEN_LIMIT -ErrorAction SilentlyContinue

# Full
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
type eval\reports\PHASE1B_SUMMARY_FOR_AGENT.txt
.\scripts\phase_gate.ps1 -Phase 1c
```

## Never

- `scripts/run_phase1b_eval.ps1` (4-sweep, 1+ hour)
- Agent shell for 30+ min jobs — user runs these
```

---

## `config/council/studypilot-board.yaml`

```yaml
council:
  name: StudyPilot Engineering Board
  agents:
    - id: lead_chairman
      role: Lead orchestrator
      expertise: [phase_gates, merges, docs]
    - id: agent_b
      role: Ingest
      expertise: [pdf_extract, ocr, chunker]
    - id: agent_c
      role: Retrieval
      expertise: [hybrid_search, rerank, gate, golden_set]
    - id: agent_d
      role: API
      expertise: [pipeline, generate, exam_services]
    - id: agent_e
      role: Web
      expertise: [react, student_mode, exam_ui]
  rules:
    council_required_for:
      - retrieve.py
      - rerank.py
      - gate.py
      - golden_set.jsonl
      - api-contracts.md
```

---

## `.cursor/rules/council-governance.mdc`

```markdown
---
description: Council Stage 2 required for risky paths
alwaysApply: true
---

# Council governance

Read `docs/COUNCIL_ORCHESTRATION.md` before merging retrieval, schema, or golden set changes.

- Stage 2 review required for retrieve/rerank/gate/golden_set/api-contracts
- Eval: `run_phase1b_eval_fast.ps1` only; maintain 100% precision@5 + OOC 10/10
- Max 2–3 workers; one file one owner
```

Paste into `.cursor/rules/council-governance.mdc`.
