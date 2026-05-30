# Lead orchestrator playbook

StudyPilot v2 uses a **lead orchestrator** (human or lead agent) to delegate work to 2–3 parallel agents max, merge slices, and hold **user gates** between phases. This doc is the source of truth for phase boundaries, file ownership, and merge policy.

**Related:** [AGENTS.md](../AGENTS.md) (worker agent instructions), [MULTI_AGENT_WORKFLOW.md](MULTI_AGENT_WORKFLOW.md) (lead + worker chats without Multitask; prompts), [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md), [api-contracts.md](api-contracts.md) (frozen interfaces), [failures-checklist.md](failures-checklist.md) (do-not-repeat rules).

---

## Roles

| Role | Responsibility |
|------|----------------|
| **Orchestrator (lead)** | Approve phase plans, assign agents, resolve contract conflicts, merge branches, run phase gates, update golden set only when eval proves a fix |
| **Worker agents (A–E)** | Implement one vertical slice within exclusive file ownership; never edit out-of-scope paths |
| **Human (you)** | Gate 1: approve plan + ownership before agents start. Gate 2: approve merge after `scripts/phase_gate.ps1` passes |

### Agent slots (Path A Part 10)

| Agent | Phase | Owns (exclusive) | Must NOT touch |
|-------|-------|------------------|----------------|
| **A — Shell** | 0b | `docker-compose.yml`, `docker/`, Alembic `001`, `eval/` stubs, pytest wiring | `app/services/rag/*` |
| **Human** | 0a | `eval/golden_set.jsonl`, `eval/pdf_audit.md` | — |
| **B — Ingest** | 1a | `pdf_extract.py`, `chunker/`, `ingestion.py`, `cli/ingest.py`, ingest tests | `rag/retrieve.py`, `rag/generate.py`, `apps/web/` |
| **C — Retrieval** | 1b | `rag/retrieve.py`, `rag/rerank.py`, `rag/gate.py`, retrieval tests | `chunker/`, `ingestion.py`, `generate.py`, `apps/web/` |
| **D — Generation** | 1c | `rag/generate.py`, `rag/pipeline.py`, cost caps in `config.py` | `chunker/`, `retrieve.py` internals without orchestrator sign-off |
| **Human + 1 agent** | 1 eval | Threshold tuning on golden set | New features |
| **E — Web** | 2 | `apps/web/*` only | API except paths frozen in `docs/api-contracts.md` |

**Max parallel agents:** 2–3. Never assign two agents to the same file.

---

## Phase gates

Run from repo root:

```powershell
.\scripts\phase_gate.ps1 -Phase 0    # after Phase 0
.\scripts\phase_gate.ps1 -Phase 1a   # after ingest slice
.\scripts\phase_gate.ps1 -Phase 1b   # after retrieval wiring
.\scripts\phase_gate.ps1 -Phase 1c   # eval green — blocks feature work
.\scripts\phase_gate.ps1 -Phase 2    # before UI demo sign-off
```

| Phase | Entry criteria | Exit gate (all required) | User gate |
|-------|----------------|--------------------------|-----------|
| **0a** | Real PPL PDFs exported | 50 rows in `golden_set.jsonl`; 10 OOC; categories documented in `eval/README.md` | Human commits golden set |
| **0b** | 0a done | `alembic upgrade head`; pytest smoke pass; eval stub runs | Orchestrator merges Agent A |
| **1a** | 0b + contracts frozen | Ingest fixture PDFs → `status=ready`; chunks + embeddings in DB; ingest E2E tests pass | Human approves before 1b parallel work |
| **1b** | 1a + `api-contracts.md` signed off | `replay_retrieval.py` completes; retrieval unit tests pass (metrics may still fail) | Orchestrator merges Agent C |
| **1c** | 1b merged | **precision@5 ≥ 70%**; **OOC refusal 10/10**; ingest ready ≥ 90%; pytest pass | Human sign-off — **no new features until green** |
| **2** | 1c green | UI demo; contract tests for API; integration test ingest→query | Human demo approval |

Phase 1a (ingest) and Phase 1b (retrieval) may run **in parallel only after** `docs/api-contracts.md` is frozen and both agents have separate branches/worktrees.

---

## File ownership matrix

Paths are **exclusive** unless listed as shared read-only.

| Path | Owner phase | Notes |
|------|-------------|-------|
| `eval/golden_set.jsonl` | Human (0a) | Read-only for all agents |
| `eval/replay_retrieval.py`, `eval/score_precision.py` | Orchestrator / eval agent | Workers may fix wiring only with orchestrator approval |
| `docs/failures-checklist.md`, `docs/api-contracts.md` | Orchestrator | Workers propose PRs; orchestrator merges contract changes |
| `docs/orchestrator.md`, `AGENTS.md` | Orchestrator | This playbook |
| `apps/api/app/services/pdf_extract.py`, `chunker/`, `ingestion.py` | Agent B (1a) | |
| `apps/api/app/services/rag/retrieve.py`, `rerank.py`, `gate.py` | Agent C (1b) | |
| `apps/api/app/services/rag/generate.py`, `pipeline.py` | Agent D (1c) | |
| `apps/api/app/models.py`, `alembic/versions/*` | Orchestrator | Schema changes require contract update first |
| `apps/api/app/config.py` | Shared | Agent D owns LLM cost caps; others read-only |
| `apps/api/app/main.py`, routers | Orchestrator → Agent D/E | No parallel edits |
| `apps/web/**` | Agent E (2) | After API contracts frozen |
| `docker-compose.yml`, `docker/` | Agent A (0b) | |
| `scripts/*.ps1` | Orchestrator | |

---

## Merge rules

1. **One branch per agent slice** — e.g. `agent-b/phase-1a-ingest`, `agent-c/phase-1b-retrieval`. Prefer git worktree isolation.
2. **Gate 1 (pre-code):** Orchestrator posts task card: allowed files, acceptance command, dependencies. Human approves.
3. **Gate 2 (pre-merge):** Agent runs scoped tests locally; orchestrator runs `phase_gate.ps1` on integrated branch.
4. **Merge order:** 0b → 1a → 1b → 1c → 2. When parallel: merge **ingest (1a) first**, then **retrieval (1b)** so replay hits real chunks.
5. **Conflict resolution:** If two slices touch the same file, **stop** — reassign or serialize. Never "merge both edits" on `pipeline.py`, `retrieve.py`, or `models.py`.
6. **Contract changes:** Any change to `docs/api-contracts.md` or DB schema requires orchestrator + human approval; bump contract version in that file.
7. **Commits:** Small, scoped commits. No `git add .`. No secrets in commits.

---

## When to parallelize vs serialize

### Parallelize (max 2–3 agents)

- **1a ingest + 1b retrieval prep** after `api-contracts.md` is frozen — retrieval agent implements against contract + mocks while ingest lands in DB.
- **Read-only explore subagents** — unlimited audits in parallel (no writes).
- **Phase 2 UI (E)** while orchestrator hardens API tests — only if HTTP contracts unchanged.

### Serialize (mandatory)

- **Schema / Alembic** — one migration owner at a time.
- **Same directory ownership** — never two agents on `rag/` or `chunker/` simultaneously.
- **Generation (1c)** after retrieval replay runs end-to-end.
- **Eval threshold tuning** — one agent iterates on golden failures at a time to avoid thrashing.
- **Contract amendments** — freeze → implement → verify; no mid-flight contract edits by workers.

---

## Kill criteria (abort agent)

Stop and reassign if the agent:

- Edits files outside its ownership matrix
- Same test fails **2+** fix cycles without orchestrator review
- Stuck **3+** iterations on one failure mode
- Adds features before Phase 1c gate is green
- Introduces OpenRouter embeddings, vector-only search, or past_paper in Study retrieval (see failures checklist)

---

## Orchestrator checklist (per phase)

### Before delegating

- [ ] Worker read `eval/golden_set.jsonl` and `docs/failures-checklist.md`
- [ ] Task card lists allowed paths and `-Phase` gate command
- [ ] Branch/worktree created; base is latest green gate
- [ ] If parallel: contracts version noted in task card

### Before merging

- [ ] Diff limited to owned paths (+ orchestrator-approved shared files)
- [ ] `.\scripts\phase_gate.ps1 -Phase <n>` PASS
- [ ] No edits to `.cursor/plans/*.plan.md`
- [ ] Human Gate 2 approval recorded

### After Phase 1c green

- [ ] Log misses in `eval/reports/` for chunk inspector design
- [ ] Unblock Phase 2 Agent E with frozen API section from `api-contracts.md`

---

## Cursor multitask patterns

See [.cursor/rules/orchestrator.mdc](../.cursor/rules/orchestrator.mdc) for delegation hints:

- **explore** — read-only audits (golden set gaps, ingest quality)
- **shell** — Docker, Alembic, pytest, `phase_gate.ps1`
- **generalPurpose** — single vertical slice with explicit file list in prompt

Do **not** launch 5+ writing agents; review becomes the bottleneck.

**Prompt template for worker agents:**

```
You are Agent <B|C|D|E> for studypilot-v2 Phase <phase>.
Read first: eval/golden_set.jsonl, docs/failures-checklist.md, docs/api-contracts.md, AGENTS.md.
Own only: <file list from matrix>.
Acceptance: .\scripts\phase_gate.ps1 -Phase <phase>
Do not edit: <forbidden paths>
```
