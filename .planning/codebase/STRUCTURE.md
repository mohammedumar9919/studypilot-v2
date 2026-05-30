# Codebase Structure

**Analysis Date:** 2026-05-30

## Directory Layout

```
studypilot-v2/
├── apps/
│   ├── api/                    # FastAPI backend (Python 3.11+)
│   │   ├── app/
│   │   │   ├── main.py         # HTTP entry — query + exam routes
│   │   │   ├── config.py       # Settings (retrieval, LLM, DB)
│   │   │   ├── database.py     # SQLAlchemy engine + get_session
│   │   │   ├── models.py       # ORM: courses, documents, chunks, embeddings
│   │   │   ├── cli/            # Offline CLIs (ingest, topic_frequency)
│   │   │   └── services/
│   │   │       ├── ingestion.py
│   │   │       ├── embedder.py
│   │   │       ├── pdf_extract.py
│   │   │       ├── chunker/      # Agent B — hierarchical chunking
│   │   │       ├── rag/          # Agents C + D — retrieve → answer
│   │   │       └── exam/         # Phase 3C — topic frequency
│   │   ├── alembic/              # DB migrations (001_core.py)
│   │   ├── tests/                # pytest suite
│   │   ├── pyproject.toml
│   │   └── .env.example          # Env template (never commit .env)
│   └── web/                      # Agent E — React + Vite SPA
│       ├── src/
│       │   ├── main.tsx          # React mount
│       │   ├── App.tsx           # Page layout
│       │   ├── api/              # fetch client
│       │   ├── components/       # UI panels
│       │   ├── hooks/            # useStudyQuery
│       │   ├── constants/        # golden miss hints
│       │   ├── utils/
│       │   └── types.ts
│       └── vite.config.ts        # Dev proxy → API :8001
├── eval/                         # Golden set + replay/scoring
│   ├── golden_set.jsonl          # 50 PPL questions (read-only for agents)
│   ├── replay_retrieval.py
│   ├── score_precision.py
│   ├── fixtures/ppl/             # Outline + PYQ seed YAML
│   └── reports/                  # Eval output (latest.jsonl, summaries)
├── scripts/                      # Orchestrator — PowerShell gates + ingest
│   ├── phase_gate.ps1
│   ├── run_phase1b_eval_fast.ps1
│   ├── ingest_ppl.ps1
│   └── ingest_ppl_pyq.ps1
├── docs/                         # Governance + contracts
│   ├── CURRENT_STATE.md          # Phase status (source of truth)
│   ├── api-contracts.md          # Frozen B/C/D/E interfaces
│   ├── orchestrator.md           # Ownership + phase gates
│   └── MULTI_AGENT_WORKFLOW.md
├── docker/                       # Postgres init SQL
├── docker-compose.yml            # pgvector Postgres on :5433
├── config/council/               # Agent persona YAML for council review
├── AGENTS.md                     # Worker agent rules + ownership table
└── .planning/codebase/           # GSD codebase maps (this folder)
```

## Directory Purposes

**`apps/api/app/services/rag/`:**
- Purpose: Study-mode RAG pipeline — retrieval through generation.
- Contains: `retrieve.py`, `rerank.py`, `gate.py`, `context.py`, `generate.py`, `pipeline.py`.
- Key files: `pipeline.py` (orchestrator), `retrieve.py` (`RetrievedChunk`, hybrid search, `replay_golden_set`).
- Owner: Agent C (`retrieve`, `rerank`, `gate`); Agent D (`generate`, `pipeline`).

**`apps/api/app/services/chunker/`:**
- Purpose: PDF page text → parent/child chunk structures.
- Contains: `base.py` (doc_kind specs, token estimates), `hierarchical.py` (`chunk_pages`).
- Key files: `hierarchical.py`.
- Owner: Agent B.

**`apps/api/app/services/exam/`:**
- Purpose: Exam intelligence — PYQ topic frequency without LLM.
- Contains: `topic_frequency.py` (`compute_topic_frequency`).
- Key files: `topic_frequency.py`; wired in `main.py` and `cli/topic_frequency.py`.
- Owner: Orchestrator / shared (Phase 3C); reads `past_paper` only.

**`apps/api/app/cli/`:**
- Purpose: Command-line entry points for batch/offline operations.
- Contains: `ingest.py`, `topic_frequency.py`.
- Key files: `ingest.py` — `python -m app.cli.ingest`.

**`apps/api/tests/`:**
- Purpose: pytest coverage per agent slice.
- Contains: `test_ingest_e2e.py` (B), `test_retrieval_golden.py`, `test_gate_refusal.py` (C), `test_generate.py`, `test_query_api.py` (D), `test_topic_frequency.py` (3C), `conftest.py`, `test_smoke.py`.
- Key files: Run from `apps/api` with Postgres on `:5433`.

**`apps/web/src/components/`:**
- Purpose: UI panels for query, answer, debug, TOC browse.
- Contains: `QueryForm.tsx`, `AnswerPanel.tsx`, `SourcesList.tsx`, `DebugPanel.tsx`, `TocBrowser.tsx`, `ChunkInspector.tsx`, `IngestBanner.tsx`, `ProgressIndicator.tsx`.
- Key files: `TocBrowser.tsx` renders `retrieval_debug.chunks` from query response.
- Owner: Agent E.

**`eval/`:**
- Purpose: Accuracy baseline — golden questions, replay harness, scoring.
- Contains: `golden_set.jsonl`, `replay_retrieval.py`, `score_precision.py`, `fixtures/ppl/`, `reports/`.
- Key files: `fixtures/ppl/ppl_outline.yaml`, `fixtures/ppl/ppl_pyq_seed.yaml`.
- Owner: Human (golden set); orchestrator (scripts); Agent C (replay wiring).

**`scripts/`:**
- Purpose: Human-run phase gates and fixture ingest automation.
- Contains: `phase_gate.ps1`, eval runners, PPL ingest wrappers.
- Key files: `run_phase1b_eval_fast.ps1` — primary eval path per `CURRENT_STATE.md`.

**`docs/`:**
- Purpose: Orchestration, contracts, phase status, task cards.
- Contains: `CURRENT_STATE.md`, `api-contracts.md`, `AGENTS.md` cross-refs, council docs.
- Key files: Read `CURRENT_STATE.md` first in every new chat.

## Key File Locations

**Entry Points:**
- `apps/api/app/main.py`: FastAPI app — `/health`, `/api/v1/query`, `/api/v1/courses/{id}/exam/topic-frequency`
- `apps/api/app/cli/ingest.py`: PDF ingest CLI
- `apps/api/app/cli/topic_frequency.py`: Exam frequency CLI
- `apps/web/src/main.tsx`: React bootstrap
- `eval/replay_retrieval.py`: Golden-set retrieval replay
- `scripts/phase_gate.ps1`: Phase verification gate

**Configuration:**
- `apps/api/app/config.py`: All runtime settings (DB, RRF, rerank, gate, OpenRouter)
- `apps/api/.env.example`: Required env var names (copy to `.env` — do not commit)
- `apps/api/alembic.ini`: Migration config
- `docker-compose.yml`: Postgres service definition
- `apps/web/vite.config.ts`: Dev server port 5173 + API proxy

**Core Logic:**
- `apps/api/app/services/ingestion.py`: Ingest orchestrator (Agent B)
- `apps/api/app/services/rag/pipeline.py`: Study query orchestrator (Agent D)
- `apps/api/app/services/rag/retrieve.py`: Hybrid retrieval + eval replay (Agent C)
- `apps/api/app/services/exam/topic_frequency.py`: PYQ frequency analytics

**Data / Schema:**
- `apps/api/app/models.py`: SQLAlchemy ORM models
- `apps/api/alembic/versions/001_core.py`: Initial schema (pgvector, tsvector)
- `eval/fixtures/ppl/ppl_outline.yaml`: PPL unit/section page map
- `eval/fixtures/ppl/ppl_pyq_seed.yaml`: Hand-labeled PYQ questions (~50 est.)

**Testing:**
- `apps/api/tests/`: Unit/integration tests (scoped by agent ownership)
- `eval/golden_set.jsonl`: 50-question eval corpus
- `eval/score_precision.py`: precision@5 + OOC scoring

**Web API client:**
- `apps/web/src/api/queryClient.ts`: `postStudyQuery` → `POST /api/v1/query`
- `apps/web/src/hooks/useStudyQuery.ts`: Query state machine + timer
- `apps/web/src/types.ts`: `QueryRequest`, `QueryResponse`, `QueryStage`

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` under `app/services/` and `app/cli/`
- Python tests: `test_<area>.py` in `apps/api/tests/`
- React components: `PascalCase.tsx` in `apps/web/src/components/`
- React hooks: `useCamelCase.ts` in `apps/web/src/hooks/`
- Fixtures: `{course}_{purpose}.yaml` in `eval/fixtures/{course}/` (e.g. `ppl_outline.yaml`)
- Scripts: `snake_case.ps1` in `scripts/`

**Directories:**
- Agent-owned subtrees match role: `chunker/` (B), `rag/` (C/D), `exam/` (3C), `apps/web/` (E)
- Service layer under `app/services/` — no separate `routers/` yet; routes live in `main.py`

**Functions:**
- Python: `snake_case` — public pipeline functions prefixed by verb (`run_study_query`, `fetch_hybrid_candidates`, `compute_topic_frequency`)
- Private helpers: leading underscore (`_rrf_fuse`, `_build_retrieval_debug`)
- TypeScript: `camelCase` for functions/variables; `PascalCase` for components and types

**Types:**
- Python: `@dataclass` for pipeline DTOs (`RetrievedChunk`, `StudyQueryResult`); Pydantic for HTTP models in `main.py`
- TypeScript: `interface`/`type` exported from `apps/web/src/types.ts`

**Database:**
- Tables: plural snake_case (`chunk_parents`, `chunk_embeddings`)
- ORM metadata column: Python attr `metadata_` maps to DB column `metadata` (`models.py:49`, `65`)
- Course IDs: uppercase strings (e.g. `PPL`)
- doc_kind: lowercase snake (`notes`, `textbook`, `syllabus`, `past_paper`)

## Where to Add New Code

**New RAG retrieval tuning (Agent C):**
- Primary code: `apps/api/app/services/rag/retrieve.py`, `rerank.py`, `gate.py`
- Tests: `apps/api/tests/test_retrieval_golden.py`, `test_gate_refusal.py`
- Do not edit: `ingestion.py`, `chunker/**`, `apps/web/**`

**New LLM / pipeline behavior (Agent D):**
- Primary code: `apps/api/app/services/rag/generate.py`, `pipeline.py`
- Config knobs: `apps/api/app/config.py` (LLM budget tiers, model names)
- HTTP wiring: `apps/api/app/main.py` (orchestrator approval — shared with E for new routes)
- Tests: `apps/api/tests/test_generate.py`, `test_query_api.py`

**New ingest / chunking behavior (Agent B):**
- Primary code: `apps/api/app/services/ingestion.py`, `pdf_extract.py`, `chunker/hierarchical.py`
- CLI: `apps/api/app/cli/ingest.py`
- Tests: `apps/api/tests/test_ingest_e2e.py`, `test_chunker.py`

**New exam intelligence endpoint:**
- Service logic: `apps/api/app/services/exam/` (new module alongside `topic_frequency.py`)
- Route: `apps/api/app/main.py` — follow `GET .../exam/topic-frequency` pattern
- Fixtures: `eval/fixtures/{course}/` for seed YAML
- Tests: `apps/api/tests/test_<feature>.py`
- Contract: update `docs/api-contracts.md` with orchestrator approval

**New web UI feature (Agent E):**
- Components: `apps/web/src/components/`
- Hooks: `apps/web/src/hooks/`
- API client: `apps/web/src/api/` (add functions per endpoint)
- Types: `apps/web/src/types.ts`
- Do not edit: `apps/api/app/services/rag/**` without contract change

**New API route (orchestrator + D/E):**
- Handler: `apps/api/app/main.py`
- Pydantic models: co-located in `main.py` (current pattern)
- Update: `docs/api-contracts.md` before parallel agent work

**New eval fixture or scorer:**
- Golden rows: `eval/golden_set.jsonl` (human approval only)
- Replay/score: `eval/replay_retrieval.py`, `eval/score_precision.py`
- Reports output: `eval/reports/`

**New DB migration:**
- Migration: `apps/api/alembic/versions/` (orchestrator-owned)
- Models: `apps/api/app/models.py`
- Requires: `docs/api-contracts.md` version bump first

**New course outline / PYQ seed:**
- Outline: `eval/fixtures/{course}/{course}_outline.yaml`
- PYQ seed: `eval/fixtures/{course}/{course}_pyq_seed.yaml`
- Register paths in `ingestion.py` (`OUTLINE_BY_FILENAME`) and `topic_frequency.py` (`_OUTLINE_PATHS`, `_SEED_PATHS`)

## Special Directories

**`apps/api/.venv/`:**
- Purpose: Local Python virtualenv for API dependencies.
- Generated: Yes (local dev).
- Committed: No.

**`apps/web/node_modules/`:**
- Purpose: npm dependencies for React app.
- Generated: Yes.
- Committed: No.

**`eval/reports/`:**
- Purpose: Eval run artifacts (`latest.jsonl`, threshold summaries, pytest logs).
- Generated: Yes (by scripts and replay).
- Committed: Often present for agent handoff; treat as run output not source.

**`.cursor/`:**
- Purpose: Cursor agents, GSD workflows, council skills, orchestrator rules.
- Generated: Partially (GSD sync).
- Committed: Yes — governance for multi-agent work.

**`.planning/`:**
- Purpose: GSD planning artifacts and codebase maps.
- Generated: By GSD commands.
- Committed: Yes (codebase maps consumed by plan/execute phases).

**`docker/pgdata` (volume):**
- Purpose: Persistent Postgres data via Docker volume `pgdata`.
- Generated: Yes (`docker compose up`).
- Committed: No.

## Multi-Agent Ownership Quick Reference

| Agent | Owns | Phase / status |
|-------|------|----------------|
| **B** | `pdf_extract.py`, `chunker/**`, `ingestion.py`, `cli/ingest.py`, ingest tests | 1a — **DONE** |
| **C** | `rag/retrieve.py`, `rag/rerank.py`, `rag/gate.py`, retrieval tests | 1b/1c — **DONE** (100% precision@5) |
| **D** | `rag/generate.py`, `rag/pipeline.py`, LLM config fields, `main.py` routes | Post-1c — **DONE** (query API live) |
| **E** | `apps/web/**` | 2 / 3C-C — heatmap UI **IN PROGRESS** |
| **Lead** | `docs/**`, `scripts/**`, merges, schema with contract bump | All phases |

One file, one owner. Forbidden cross-edits documented in `AGENTS.md` and `docs/orchestrator.md`.

## Runtime Layout (dev)

| Service | Port | Path |
|---------|------|------|
| Postgres (pgvector) | 5433 | `docker-compose.yml` |
| FastAPI | 8001 | `apps/api` |
| Vite dev | 5173 | `apps/web` (proxies `/api` → 8001) |

Per `docs/CURRENT_STATE.md`: re-eval after retrieval changes with `scripts/run_phase1b_eval_fast.ps1` and `$env:MIN_RERANK_SCORE = "0.35"`.

---

*Structure analysis: 2026-05-30*
