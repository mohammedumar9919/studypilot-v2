# New Chat Bootstrap Prompts

Copy prompts into **fresh Cursor chats**. Keep **Multitask Mode OFF** unless you explicitly want background workers.

**Full guide:** [MULTI_AGENT_WORKFLOW.md](MULTI_AGENT_WORKFLOW.md)

---

## Which prompt to use?

| Situation | Prompt section |
|-----------|----------------|
| Starting orchestration for a phase | [Lead orchestrator](#1-lead-orchestrator-new-chat) |
| Lead assigned a task card | [Worker agent](#2-worker-agent-new-chat) |
| Read-only analysis | [Explore-only](#3-explore-only-no-edits) |
| Continuing after worker done | [Back to lead](#4-return-to-lead-same-chat) |
| Fast start with eval already run | [Minimal lead](#5-minimal-lead-eval-already-pasted) |

**Attach / @-mention:** For lead, `@docs/CURRENT_STATE.md` and `@docs/LEAD_ORCHESTRATOR.md`. For workers, @ files listed in OWN ONLY.

---

## 1. Lead orchestrator (new chat)

```
You are the LEAD ORCHESTRATOR for StudyPilot v2 (repo: C:\Projects\studypilot-v2).

Read in order:
1. docs/CURRENT_STATE.md
2. docs/LEAD_ORCHESTRATOR.md
3. docs/MULTI_AGENT_WORKFLOW.md
4. AGENTS.md
5. docs/api-contracts.md
6. C:\Users\Owner\.cursor\plans\path_a_lean_rebuild_0f4ce0e9.plan.md — Part 10 and Part 11 ONLY (read-only)

Rules:
- Do NOT edit C:\Users\Owner\.cursor\plans\*.plan.md
- Phase 0, 1a, 1b CODE IS DONE — do not rebuild unless proven bug
- Current target: Phase 1c eval gate (precision@5 >= 70%, OOC 10/10)
- Use scripts/run_phase1b_eval_fast.ps1 ONLY — never run_phase1b_eval.ps1
- I run Docker, pytest, and eval in MY PowerShell — you analyze pasted reports
- Delegate implementation via TASK CARDS for separate worker chats (see MULTI_AGENT_WORKFLOW.md)
- Max 2 active workers; one file, one owner
- Update docs/CURRENT_STATE.md when status changes

First response:
1. State phase/blocker from CURRENT_STATE.md
2. Ask for eval/reports/PHASE1B_SUMMARY_FOR_AGENT.txt OR give terminal commands
3. Propose next step — no Phase 2 until phase_gate.ps1 -Phase 1c PASS
```

---

## 2. Worker agent (new chat)

Paste the task card from lead. Template:

```
You are Agent AGENT_SLOT for studypilot-v2 Phase PHASE.

Read first:
- docs/CURRENT_STATE.md
- AGENTS.md
- docs/api-contracts.md
- docs/failures-checklist.md

OWN ONLY:
- (paths)

FORBIDDEN:
- (paths)
- .cursor/plans/**

Task:
(DESCRIPTION)

When done: list files changed, 3-5 bullet summary, exact verify commands for my terminal.
```

See filled examples in [MULTI_AGENT_WORKFLOW.md](MULTI_AGENT_WORKFLOW.md#prompt-2--worker-agent-new-chat-per-task).

---

## 3. Explore-only (no edits)

```
Read-only. Do NOT edit any files.

Read: eval/golden_set.jsonl, eval/reports/latest.jsonl, docs/CURRENT_STATE.md

Task: Analyze retrieval misses — table of id, expected pages, retrieved pages, likely cause.

Output markdown table only for the lead orchestrator chat.
```

---

## 4. Return to lead (same chat)

```
Worker Agent SLOT completed.

Summary:
(paste worker reply)

Eval (if run):
(paste eval/reports/PHASE1B_SUMMARY_FOR_AGENT.txt)

Next: phase_gate or another task card?
```

---

## 5. Minimal lead (eval already pasted)

```
Lead orchestrator for C:\Projects\studypilot-v2.
Read docs/CURRENT_STATE.md only first.
Phase 1c only. Do not redo Phase 0–1b. Do not edit .cursor/plans.

Latest eval:
(paste PHASE1B_SUMMARY_FOR_AGENT.txt)

Propose: confirm MIN_RERANK_SCORE, fix top misses via worker task card if needed, then Phase 2 plan after gate PASS.
```

---

## After pasting (you, in terminal)

```powershell
cd C:\Projects\studypilot-v2
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"

# Smoke (~2 min)
$env:GOLDEN_LIMIT = "10"
$env:MIN_RERANK_SCORE = "0.40"
.\scripts\run_phase1b_eval_fast.ps1
Remove-Item Env:GOLDEN_LIMIT -ErrorAction SilentlyContinue

# Full (~5–15 min)
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
type eval\reports\PHASE1B_SUMMARY_FOR_AGENT.txt
.\scripts\phase_gate.ps1 -Phase 1c
```

Paste reports back into the **lead** chat.
