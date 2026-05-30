# Technology Stack

**Analysis Date:** 2026-05-30

## Languages

**Primary:**
- **Python 3.11+** — Backend API, ingestion, RAG pipeline, eval replay, Alembic migrations (`apps/api/`, `eval/*.py`)
- **TypeScript ~6.0** — React frontend (`apps/web/src/**/*.ts`, `apps/web/src/**/*.tsx`)

**Secondary:**
- **PowerShell** — Operational scripts for Docker, ingest, eval gates (`scripts/*.ps1`)
- **YAML** — Council board, PPL outline/PYQ seed fixtures (`config/council/`, `eval/fixtures/ppl/`)
- **SQL** — Postgres schema via Alembic (`apps/api/alembic/versions/001_core.py`, `docker/init-databases.sql`)

## Runtime

**Environment:**
- **Python 3.11** — Declared in `apps/api/pyproject.toml` (`requires-python = ">=3.11"`, Ruff `target-version = "py311"`)
- **Node.js** — Required for Vite/React dev server (`apps/web/`); no `.nvmrc` at repo root
- **Docker** — Postgres + pgvector container (`docker-compose.yml`)

**Package Manager:**
- **pip + setuptools** — API install via editable package (`pip install -e ".[dev]"` or `".[dev,ocr]"` in `apps/api/`)
- **npm** — Frontend dependencies (`apps/web/package.json`, lockfile: `apps/web/package-lock.json` present)

## Frameworks

**Core:**
- **FastAPI ≥0.115** — HTTP API (`apps/api/app/main.py`)
- **Uvicorn[standard] ≥0.32** — ASGI server (dev: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8001` per `apps/web/README.md`)
- **React 19.2** + **React DOM 19.2** — SPA UI (`apps/web/src/App.tsx`, `apps/web/src/main.tsx`)
- **Vite 8** — Dev server and build (`apps/web/vite.config.ts`, port **5173**)

**Data / ORM:**
- **SQLAlchemy 2.0** — Models and sessions (`apps/api/app/models.py`, `apps/api/app/database.py`)
- **Alembic 1.14** — Migrations (`apps/api/alembic/`, `apps/api/alembic.ini`)
- **psycopg 3.2** — PostgreSQL driver (`postgresql+psycopg://` URLs)
- **pgvector 0.3.6** — Vector column type and SQLAlchemy integration (`apps/api/app/models.py`, migration `001_core.py`)

**RAG / ML (local, CPU):**
- **fastembed ≥0.4** — Local text embeddings (`apps/api/app/services/embedder.py`, model `BAAI/bge-small-en-v1.5`)
- **fastembed TextCrossEncoder** — Local reranking (`apps/api/app/services/rag/rerank.py`, model `BAAI/bge-reranker-base`)
- **tiktoken ≥0.8** — Token estimation in chunker (`apps/api/app/services/chunker/`)

**Document processing:**
- **PyMuPDF (fitz) ≥1.24** — PDF text extraction (`apps/api/app/services/pdf_extract.py`)
- **pytesseract + Pillow** (optional `[ocr]` extra) — OCR for low-text pages (`apps/api/pyproject.toml` optional-deps `ocr`)

**HTTP client:**
- **httpx ≥0.28** — OpenRouter chat completions (`apps/api/app/services/rag/generate.py`)

**Config / validation:**
- **pydantic-settings ≥2.6** — Environment-backed settings (`apps/api/app/config.py`)
- **PyYAML ≥6** — Outline and council YAML (`apps/api/app/services/pdf_extract.py`, `config/council/studypilot-board.yaml`)

**Testing:**
- **pytest ≥8.3** + **pytest-asyncio ≥0.24** — API tests (`apps/api/tests/`, `apps/api/pyproject.toml` `[tool.pytest.ini_options]`)
- **Eval Python scripts** — Golden-set replay and scoring (`eval/replay_retrieval.py`, `eval/score_precision.py`); no separate JS test runner configured

**Linting / formatting:**
- **Ruff ≥0.8** — Python linter/formatter (`apps/api/pyproject.toml`, line-length 100)
- **ESLint 10** + **typescript-eslint 8** — Frontend (`apps/web/eslint.config.js`)

**Build / Dev:**
- **setuptools** — API package build (`apps/api/pyproject.toml` `[build-system]`)
- **@vitejs/plugin-react 6** — React HMR (`apps/web/vite.config.ts`)

## Key Dependencies

**Critical (RAG path):**
| Package | Role | Where |
|---------|------|-------|
| `fastapi`, `uvicorn` | API surface | `apps/api/app/main.py` |
| `sqlalchemy`, `psycopg`, `pgvector` | Persistence + vectors | `apps/api/app/models.py`, `retrieve.py` |
| `fastembed` | Embeddings + cross-encoder rerank | `embedder.py`, `rerank.py` |
| `pymupdf` | PDF ingest | `pdf_extract.py` |
| `httpx` | LLM generation (external) | `generate.py` |
| `tiktoken` | Chunk token counts | `chunker/` |
| `python-multipart` | Future upload support | `pyproject.toml` |

**Infrastructure:**
- **pgvector/pgvector:pg16** — Docker image for Postgres 16 + vector extension (`docker-compose.yml`)
- **react**, `vite`, `typescript` — Frontend stack (`apps/web/package.json`)

**Not used for embeddings/generation:**
- No OpenAI/Anthropic SDK in application code; chat goes through OpenRouter REST only.

## Configuration

**Environment:**
- API settings via **pydantic-settings** reading `apps/api/.env` (`Settings.model_config` in `apps/api/app/config.py`)
- Example template: `apps/api/.env.example` (database, embedding model, OCR threshold)
- `.env` file present under `apps/api/` (not committed; do not read contents in docs)
- Eval scripts set `DATABASE_URL` and optionally `MIN_RERANK_SCORE`, `GOLDEN_LIMIT` in PowerShell (`scripts/run_phase1b_eval_fast.ps1`)

**Key settings (defaults in `apps/api/app/config.py`):**
| Setting | Default | Purpose |
|---------|---------|---------|
| `database_url` | `localhost:5433/studypilot` | Main DB |
| `test_database_url` | `localhost:5433/studypilot_test` | Pytest / Alembic test DB |
| `embedding_model` | `BAAI/bge-small-en-v1.5` | fastembed model |
| `embedding_dims` | `384` | Vector size |
| `rerank_model` | `BAAI/bge-reranker-base` | Cross-encoder |
| `min_rerank_score` | `0.35` | Confidence gate threshold |
| `openrouter_api_key` | `""` | Required for `/api/v1/query` generation |
| `environment` | `development` | Selects dev vs prod chat model |
| `studypilot_llm_budget` | `budget` | Token/chunk limits for generation |

**Build:**
- `apps/api/pyproject.toml` — Python project metadata and tool config
- `apps/api/alembic.ini` — Migration runner
- `apps/web/tsconfig.json`, `apps/web/tsconfig.app.json`, `apps/web/tsconfig.node.json` — TypeScript project refs
- `apps/web/vite.config.ts` — Dev proxy `/api` and `/health` → `http://localhost:8001`

**Docker:**
- `docker-compose.yml` — Single `postgres` service, host port **5433** → container 5432
- `docker/init-databases.sql` — Creates `studypilot_test` database on first boot

## Platform Requirements

**Development:**
- **Windows** — Primary workflow (absolute paths in scripts, Tesseract default `C:\Program Files\Tesseract-OCR\` in `pdf_extract.py`)
- **Docker Desktop** — For Postgres (`docker compose up -d`)
- **Python 3.11+** with venv at `apps/api/.venv`
- **Node.js + npm** — For `apps/web` (`npm run dev`, `npm run build`, `npm run lint`)
- **Tesseract OCR** (optional) — Required for `past_paper` ingest; install via winget per `scripts/ingest_ppl_pyq.ps1`
- **CPU RAM** — Cross-encoder rerank ~400MB per process (`rerank.py` comment); full golden replay ~5–10 min CPU

**Production:**
- Not detected — no Dockerfile for API/web, no K8s/terraform, no `.github/workflows` CI. `docs/CURRENT_STATE.md` lists Phase 4 targets: auth, upload API, streaming, observability.

## Repository Layout (stack-relevant)

| Path | Stack role |
|------|------------|
| `apps/api/` | FastAPI backend, venv, Alembic, pytest |
| `apps/web/` | Vite + React frontend |
| `eval/` | Golden set + Python eval harness (no LLM) |
| `scripts/` | PowerShell automation |
| `docker/` | DB init SQL |
| `config/council/` | Agent council YAML (orchestration, not runtime) |
| `docs/` | Orchestrator and contracts (not application runtime) |

## Dev Commands (reference)

```powershell
# Postgres
docker compose up -d

# API (from apps/api, venv active)
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Web (from apps/web)
npm install
npm run dev

# Ingest + eval (repo root)
.\scripts\ingest_ppl.ps1
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
.\scripts\phase_gate.ps1 -Phase 1c
```

---

*Stack analysis: 2026-05-30*
