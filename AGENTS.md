# Agent instructions (StudyPilot v2)

**New chat:** You are the **lead orchestrator**. Boot from [docs/LEAD_ORCHESTRATOR.md](docs/LEAD_ORCHESTRATOR.md) and [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md). Prompts: [docs/NEW_CHAT_PROMPT.md](docs/NEW_CHAT_PROMPT.md). Multi-agent (no Multitask): [docs/MULTI_AGENT_WORKFLOW.md](docs/MULTI_AGENT_WORKFLOW.md).

Concise rules for Cursor worker agents. The lead orchestrator uses [docs/orchestrator.md](docs/orchestrator.md) for phase gates and merge policy.

## Read first (every task)

1. [`eval/golden_set.jsonl`](eval/golden_set.jsonl) — 50 PPL questions, expected pages, 10 out-of-corpus refusals
2. [`docs/failures-checklist.md`](docs/failures-checklist.md) — do-not-repeat rules from cursortest audit
3. [`docs/api-contracts.md`](docs/api-contracts.md) — frozen schemas and function signatures (Phase 1 parallel work)
4. [`eval/README.md`](eval/README.md) — scoring rules (precision@5, OOC gate)

Do **not** edit `.cursor/plans/*.plan.md`.

## Ownership (current phase)

| If you are | You may edit | Forbidden |
|------------|--------------|-----------|
| **Agent B (1a ingest)** | `app/services/pdf_extract.py`, `chunker/**`, `ingestion.py`, `cli/ingest.py`, `tests/test_*ingest*` | `rag/retrieve.py`, `rag/generate.py`, `apps/web/**` |
| **Agent C (1b retrieval)** | `rag/retrieve.py`, `rag/rerank.py`, `rag/gate.py`, `tests/test_*retriev*` | `chunker/**`, `ingestion.py`, `generate.py`, `apps/web/**` |
| **Agent D (1c generation)** | `rag/generate.py`, `rag/pipeline.py`, LLM-related `config.py` fields | `chunker/**`, core retrieve SQL without orchestrator OK |
| **Agent E (2 web)** | `apps/web/**` | API except contract-stable routes in `api-contracts.md` |
| **Orchestrator** | `docs/**`, `scripts/**`, merges, `models.py` / Alembic with contract bump | — |

**Shared read-only:** `eval/golden_set.jsonl`, `docs/failures-checklist.md`, `docker-compose.yml` (unless Agent A).

**One file, one owner.** If your task requires a forbidden path, stop and ask the orchestrator.

## Engineering constraints

- Local **FastEmbed** only for embeddings — no OpenRouter embeddings
- **Hybrid** retrieval (pgvector + tsvector RRF) + rerank + confidence gate — no vector-only search
- **Hierarchical** parent-child chunks; Study mode excludes `past_paper` doc_kind
- **Idempotent** ingest (delete old chunks before re-index)
- pytest from `apps/api`; DB creds match `docker-compose.yml`
- No feature work before Phase 1c: **precision@5 ≥ 70%** and **10/10 OOC refusal**

## Verification

From repo root after your slice:

```powershell
cd apps\api
pytest                    # or scoped: pytest tests/test_ingest_e2e.py
cd ..\..
.\scripts\phase_gate.ps1 -Phase 1a   # use phase matching your slice
```

## Cursor delegation

Multitask patterns and subagent types: [.cursor/rules/orchestrator.mdc](.cursor/rules/orchestrator.mdc).

When spawning subagents, include the ownership table above and the exact acceptance command in the prompt.
