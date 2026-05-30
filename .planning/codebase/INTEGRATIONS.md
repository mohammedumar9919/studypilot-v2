# External Integrations

**Analysis Date:** 2026-05-30

## APIs & External Services

**LLM (chat generation only — Path A):**
- **OpenRouter** — Study answer generation via Chat Completions API
  - Implementation: `httpx` POST to `https://openrouter.ai/api/v1/chat/completions` (`apps/api/app/services/rag/generate.py`)
  - Auth: `OPENROUTER_API_KEY` (pydantic field `openrouter_api_key` in `apps/api/app/config.py`)
  - Models:
    - Development: `openrouter_dev_chat_model` default `meta-llama/llama-3.3-70b-instruct:free`
    - Production: `openrouter_chat_model` default `deepseek/deepseek-chat`
  - Selection: `settings.resolved_chat_model()` keyed off `environment`
  - Headers: `Authorization: Bearer`, `HTTP-Referer: https://studypilot.local`, `X-Title: StudyPilot v2`
  - Not used for: embeddings, reranking, or eval replay (eval is retrieval-only)

**Model hosting (implicit, first-run download):**
- **Hugging Face Hub** — fastembed downloads embedding and reranker weights on first use (`BAAI/bge-small-en-v1.5`, `BAAI/bge-reranker-base`); no explicit HF token in app config

**Not integrated:**
- No Stripe, Supabase, AWS, SendGrid, Twilio, or OAuth providers in application source
- No OpenAI/Anthropic SDK — only OpenRouter-compatible HTTP

## Data Storage

**Databases:**
- **PostgreSQL 16 + pgvector** (Docker)
  - Image: `pgvector/pgvector:pg16` (`docker-compose.yml`)
  - Host port: **5433** (maps to container 5432)
  - Credentials (compose defaults): user/db `studypilot`, password `studypilot`
  - Connection env: `DATABASE_URL`, `TEST_DATABASE_URL` (`apps/api/.env.example`, `apps/api/app/config.py`)
  - Client: SQLAlchemy 2 + psycopg3 (`apps/api/app/database.py`)
  - ORM models: `apps/api/app/models.py` (`courses`, `documents`, `chunk_parents`, `chunks`, `chunk_embeddings`)
  - Extensions: `CREATE EXTENSION vector` in Alembic `001_core.py`
  - Full-text: generated `text_tsv` column + GIN index on `chunks` for BM25-style search (`retrieve.py`)
  - Test DB: `studypilot_test` created by `docker/init-databases.sql`

**File Storage:**
- **Local filesystem only** — PDFs referenced by absolute path at ingest time (`Document.file_path` in `apps/api/app/services/ingestion.py`)
- Fixture PDFs: `eval/fixtures/ppl/PPL notes.pdf`, `eval/fixtures/ppl/PPL previous papers.pdf`
- No S3, Azure Blob, or GCS client detected

**Caching:**
- **None** — No Redis/Memcached; embedder and reranker use `@lru_cache(maxsize=1)` in-process (`embedder.py`, `rerank.py`)

## Authentication & Identity

**Auth Provider:**
- **None (current phase)** — API endpoints are unauthenticated
  - `GET /health`, `POST /api/v1/query`, `GET /api/v1/courses/{course_id}/exam/topic-frequency` (`apps/api/app/main.py`)
  - Phase 4 backlog: auth per `docs/CURRENT_STATE.md`

**API keys (service-to-service):**
- OpenRouter bearer token only for outbound LLM calls
- Database credentials via connection string (local dev defaults in compose)

## Monitoring & Observability

**Error Tracking:**
- **None** — No Sentry, Datadog, or similar SDK in `apps/api` or `apps/web`

**Logs:**
- Python `logging` in generation path (`apps/api/app/services/rag/generate.py` — token usage info)
- PDF extract warnings for OCR skips (`apps/api/app/services/pdf_extract.py`)
- Eval scripts write artifacts to `eval/reports/` (`phase1b_run.log`, `pytest_out.txt`, `latest.jsonl`)

**Metrics:**
- Eval metrics JSON: `eval/reports/phase1b_metrics.json` (precision@5, OOC refusal, gate pass flag)
- Human/agent summary: `eval/reports/PHASE1B_SUMMARY_FOR_AGENT.txt`

## CI/CD & Deployment

**Hosting:**
- **Local development only** — Documented ports: API `localhost:8001`, Web `localhost:5173`, Postgres `localhost:5433` (`docs/CURRENT_STATE.md`)

**CI Pipeline:**
- **None detected** — No `.github/workflows/` in repository root; Wave 3 plans CI eval gate (`docs/CURRENT_STATE.md`)

**Containerization:**
- **Postgres only** via `docker-compose.yml` — API and web run natively on host (venv + npm)

## Environment Configuration

**Required env vars (API — see `apps/api/.env.example` and `apps/api/app/config.py`):**

| Variable | Required when | Notes |
|----------|---------------|-------|
| `DATABASE_URL` | Always (ingest, API, eval) | Default matches Docker port 5433 |
| `TEST_DATABASE_URL` | pytest, phase gates | Separate DB `studypilot_test` |
| `OPENROUTER_API_KEY` | `POST /api/v1/query` with generation | 503 if missing (`main.py`) |
| `EMBEDDING_MODEL` | Optional override | Default `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMS` | Optional override | Default `384` |
| `OCR_CHARS_PER_PAGE_THRESHOLD` | Optional | Default `50` |
| `ENVIRONMENT` | Optional | `development` vs `production` model routing |
| `OPENROUTER_DEV_CHAT_MODEL` | Optional | Dev chat model override |
| `OPENROUTER_CHAT_MODEL` | Optional | Prod chat model override |
| `STUDYPILOT_LLM_BUDGET` | Optional | `budget` / `balanced` / `quality` tiers |
| `MIN_RERANK_SCORE` | Eval override | Maps to `min_rerank_score` via pydantic-settings |
| `GOLDEN_LIMIT` | Smoke eval | Truncates golden replay (`retrieve.py`) |

**Secrets location:**
- `apps/api/.env` — Gitignored local secrets (OpenRouter key, DB overrides)
- `apps/api/.env.example` — Committed template without secrets
- Docker compose uses inline dev credentials (not suitable for production)

**Frontend:**
- No `VITE_*` env vars; API reached via Vite dev proxy (`apps/web/vite.config.ts` → `localhost:8001`)

## Webhooks & Callbacks

**Incoming:**
- **None** — No webhook routes in `apps/api/app/main.py`

**Outgoing:**
- **OpenRouter chat completions** only (`generate.py`)
- No callback URLs, Stripe webhooks, or email triggers

## Internal Integration Points (not external, but cross-component)

**Hybrid RAG retrieval (Postgres-native):**
- Vector: pgvector cosine distance (`<=>`) in `apps/api/app/services/rag/retrieve.py`
- Lexical: PostgreSQL `ts_rank_cd` + `websearch_to_tsquery` / `to_tsquery` on `chunks.text_tsv`
- Fusion: Reciprocal Rank Fusion (`settings.rrf_k`, weights in `config.py`)
- Pipeline: retrieve → rerank → gate → context → generate (`apps/api/app/services/rag/pipeline.py`)

**Exam intelligence (no LLM):**
- `GET /api/v1/courses/{course_id}/exam/topic-frequency` — keyword frequency from PYQ ingest (`apps/api/app/services/exam/topic_frequency.py`)
- Seed data: `eval/fixtures/ppl/ppl_pyq_seed.yaml`

**Outline metadata (fixture-driven):**
- `eval/fixtures/ppl/ppl_outline.yaml` loaded during notes ingest and retrieval hints (`ingestion.py`, `retrieve.py`)

**Council / orchestration (dev process, not runtime API):**
- `config/council/studypilot-board.yaml` — Agent personas and `council_required_for` file list for human/agent review gates
- Cursor skills: `.cursor/skills/council-*`, `run-eval-gate` (`docs/TOOLING_INDEX.md`)

## PowerShell Script Integrations

| Script | Integrates with |
|--------|-----------------|
| `scripts/ingest_ppl.ps1` | Docker Postgres, Alembic, `python -m app.cli.ingest`, golden replay |
| `scripts/ingest_ppl_pyq.ps1` | OCR extra (`pip install -e ".[dev,ocr]"`), Tesseract PATH, PYQ PDF only |
| `scripts/run_phase1b_eval_fast.ps1` | Docker, pytest, `eval/replay_retrieval.py`, `eval/score_precision.py` |
| `scripts/run_phase1b_eval.ps1` | Multi-threshold sweep (discouraged; ~1+ hour) |
| `scripts/phase_gate.ps1` | Phase 0/1a/1b/1c/2 gates: pytest, replay, scoring |

## Eval Harness Integration

| Artifact | Role |
|----------|------|
| `eval/golden_set.jsonl` | 50 questions (40 in-corpus, 10 OOC) |
| `eval/replay_retrieval.py` | Calls `replay_golden_set()` — no LLM |
| `eval/score_precision.py` | precision@5 + OOC refusal vs golden |
| `eval/reports/latest.jsonl` | Per-question replay output |
| `eval/README.md` | Gate targets: precision@5 ≥ 70%, OOC 10/10 |

## Optional System Dependencies

| Dependency | Used for | Detection |
|------------|----------|-----------|
| **Tesseract OCR** | Scanned PDF pages in `past_paper` ingest | `PATH` or `C:\Program Files\Tesseract-OCR\tesseract.exe` (`pdf_extract.py`, `ingest_ppl_pyq.ps1`) |
| **Docker** | Postgres + pgvector | `docker compose` in eval/ingest scripts |

## Integration Boundaries (prescriptive)

- **Use local fastembed** for all embeddings and reranking — do not route retrieval through OpenRouter or cloud embedding APIs.
- **Use OpenRouter only in** `apps/api/app/services/rag/generate.py` for student-facing answers after the confidence gate passes.
- **Keep eval replay LLM-free** — `eval/replay_retrieval.py` and `replay_golden_set()` must not call generation.
- **Exclude `past_paper` doc_kind** from study retrieval (`STUDY_DOC_KINDS` in `retrieve.py`); PYQ is for exam analytics only.
- **Point new secrets at** `apps/api/.env` with names matching pydantic `Settings` fields (uppercase env aliases).

---

*Integration audit: 2026-05-30*
