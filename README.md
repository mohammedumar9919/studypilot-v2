# StudyPilot v2

Eval-first RAG rebuild. **PPL pilot** — local embeddings, hybrid retrieval, confidence gate.

## New chat / lead orchestrator

Start here:

1. [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) — what's done, blocked, next
2. [docs/LEAD_ORCHESTRATOR.md](docs/LEAD_ORCHESTRATOR.md) — boot sequence, gates, delegation
3. [docs/MULTI_AGENT_WORKFLOW.md](docs/MULTI_AGENT_WORKFLOW.md) — multi-agent without Multitask; prompt templates
4. [docs/NEW_CHAT_PROMPT.md](docs/NEW_CHAT_PROMPT.md) — copy-paste into fresh chats

Architecture plans (read-only): `C:\Users\Owner\.cursor\plans\path_a_lean_rebuild_0f4ce0e9.plan.md`

## Quick start (user terminal)

```powershell
# 1. Start Postgres + pgvector (port 5433)
docker compose up -d

# 2. API setup
cd apps/api
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
alembic upgrade head

# 3. Ingest PPL fixtures
cd C:\Projects\studypilot-v2
.\scripts\ingest_ppl.ps1

# 4. Phase 1c eval (fast — single threshold)
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
.\scripts\phase_gate.ps1 -Phase 1c
```

## Layout

| Path | Purpose |
|------|---------|
| `eval/` | Golden set + replay harness |
| `apps/api/` | FastAPI, ingest, RAG pipeline |
| `docs/` | Orchestrator, contracts, current state |
| `scripts/` | ingest, phase gates, fast eval |

Config: copy `apps/api/.env.example` to `.env`. Defaults match `docker-compose.yml` (port **5433**).
