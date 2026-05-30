# Coding Conventions

**Analysis Date:** 2026-05-30

## Naming Patterns

**Files (Python API):**
- Modules: `snake_case.py` under `apps/api/app/` (e.g. `apps/api/app/services/rag/pipeline.py`)
- Tests: `test_<area>.py` under `apps/api/tests/` (e.g. `apps/api/tests/test_query_api.py`)
- Alembic revisions: `apps/api/alembic/versions/001_core.py`
- CLI entrypoints: `apps/api/app/cli/ingest.py`, `apps/api/app/cli/topic_frequency.py`

**Files (React web):**
- Components: `PascalCase.tsx` in `apps/web/src/components/` (e.g. `apps/web/src/components/QueryForm.tsx`)
- Hooks: `camelCase.ts` with `use` prefix in `apps/web/src/hooks/` (e.g. `apps/web/src/hooks/useStudyQuery.ts`)
- API client: `apps/web/src/api/queryClient.ts`
- Shared types: `apps/web/src/types.ts`
- Constants: `apps/web/src/constants/goldenMisses.ts`
- Utilities: `apps/web/src/utils/pageMatch.ts`

**Functions (Python):**
- Use `snake_case` for all functions and methods (e.g. `run_study_query`, `apply_confidence_gate`, `fetch_hybrid_candidates`)
- Prefix private helpers with `_` (e.g. `_build_retrieval_debug`, `_db_available`, `_chunk` in tests)
- FastAPI route handlers match resource verbs: `health`, `query`, `exam_topic_frequency`

**Functions (TypeScript):**
- React components: `PascalCase` named exports (e.g. `export function QueryForm`)
- Hooks and utilities: `camelCase` (e.g. `useStudyQuery`, `pageHitsExpected`)
- Custom error class: `QueryApiError` in `apps/web/src/api/queryClient.ts`

**Variables:**
- Python: `snake_case` (e.g. `course_id`, `rerank_scores`, `db_session`)
- TypeScript state/props: `camelCase` (e.g. `courseId`, `debugEnabled`, `retrieval_debug` in API JSON uses snake_case — mirror backend in request/response types)

**Types:**
- Python: `@dataclass` for pipeline results (`StudyQueryResult`, `StudyQuestionResult` in `apps/api/app/services/rag/pipeline.py`); Pydantic `BaseModel` for HTTP contracts in `apps/api/app/main.py`; plain classes for extraction (`PageText`, `RetrievedChunk`)
- TypeScript: `interface` for API shapes in `apps/web/src/types.ts`; string union literals for enums (`QueryStage`, `preset: 'study'`); use `type` imports: `import type { QueryResponse } from '../types'`

## Code Style

**Python formatting:**
- Ruff configured in `apps/api/pyproject.toml`: `line-length = 100`, `target-version = "py311"`
- Run from `apps/api`: `ruff check .` and `ruff format .` (Ruff is a dev optional dependency)
- No Black or mypy config in repo; type hints are used throughout but not enforced by CI

**Python typing:**
- Add `from __future__ import annotations` at top of new modules (see `apps/api/tests/test_query_api.py`, `apps/api/app/services/rag/pipeline.py`)
- Annotate public function signatures; use `list[...]`, `dict[str, Any]`, `str | None` style unions
- Test helpers return typed factories: `_chunk() -> RetrievedChunk` in `apps/api/tests/test_query_api.py`

**TypeScript formatting:**
- No Prettier config in `apps/web/`; rely on ESLint + TypeScript compiler strictness
- `apps/web/tsconfig.app.json`: `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `verbatimModuleSyntax`, `erasableSyntaxOnly`
- Build runs `tsc -b` before Vite (`apps/web/package.json` script `build`)

**Linting:**
- Web: ESLint flat config in `apps/web/eslint.config.js` — `@eslint/js` recommended, `typescript-eslint` recommended, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh` (Vite)
- Run: `npm run lint` from `apps/web/`
- API: Ruff only (no ESLint equivalent)

## Import Organization

**Python (`apps/api/app/`):**
1. Standard library (`from __future__ import annotations`, `uuid`, `pathlib`, etc.)
2. Third-party (`fastapi`, `sqlalchemy`, `pydantic`, `httpx`)
3. Local `app.*` imports (e.g. `from app.config import settings`)
- Tests may import from `app.main`, `app.services.*`, and use `Path(__file__).resolve().parents[N]` for repo-relative fixtures

**TypeScript (`apps/web/src/`):**
1. React / `react-dom` imports
2. Relative component/hook/api imports (`./components/...`, `../api/queryClient`)
3. Type-only imports (`import type { ... } from '../types'`)
4. Side-effect CSS last (`import './App.css'`)
- Use `.tsx` extension in imports where required (`import App from './App.tsx'` in `apps/web/src/main.tsx`)

**Path aliases:**
- No TypeScript path aliases configured; use relative imports only
- Eval scripts append API root: `sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))` in `eval/replay_retrieval.py`

## Error Handling

**FastAPI routes (`apps/api/app/main.py`):**
- Validate presets at route level: unsupported `preset` → `HTTPException(400, detail=...)`
- Map domain errors to HTTP status:
  - `ValueError` → 400
  - `OpenRouterGenerationError` → 401/402/429 when `status_code` matches, else 502
  - Missing `OPENROUTER_API_KEY` in `RuntimeError` message → 503 with setup hint
- Return structured JSON via Pydantic `response_model`; do not leak stack traces to clients

**Service layer:**
- Raise `ValueError` for invalid presets/inputs in pipeline (`apps/api/app/services/rag/pipeline.py`, `apps/api/app/services/rag/generate.py`)
- Define domain-specific exceptions where mapping matters: `OpenRouterGenerationError` in `apps/api/app/services/rag/generate.py` with optional `status_code`
- Gate/refusal uses status strings (`"ok"`, `"not_in_materials"`) — not exceptions — in `apps/api/app/services/rag/gate.py`

**Database / infra:**
- `apps/api/tests/conftest.py`: catch connection failures and `pytest.skip(...)` rather than fail the suite when Postgres is down
- Phase gate (`scripts/phase_gate.ps1`) falls back to smoke pytest if full run fails with skips

**TypeScript client (`apps/web/src/api/queryClient.ts`):**
- Throw `QueryApiError` with `status` and parsed FastAPI `detail` on non-OK responses
- Hook (`apps/web/src/hooks/useStudyQuery.ts`) surfaces errors as user-readable strings; treat `AbortError` as silent cancel

## Logging

**Framework:** Python `logging` module (stdlib)

**Patterns:**
- Module-level logger: `logger = logging.getLogger(__name__)` in `apps/api/app/services/rag/generate.py`
- No structured logging library; web uses inline error UI, not console logging frameworks
- Do not log secrets or full API keys; settings load from `.env` via `apps/api/app/config.py` (`extra="ignore"`)

## Comments

**When to comment:**
- Module docstrings at top of services and test files (e.g. `"""Tests for POST /api/v1/query (mocked generation — no network)."""` in `apps/api/tests/test_query_api.py`)
- Explain non-obvious business rules: eval tolerance, doc_kind filters, phase ownership in `AGENTS.md`
- Inline comments for orchestration stubs and future API changes (e.g. SSE note in `apps/web/src/api/queryClient.ts`)

**JSDoc/TSDoc:**
- Use TSDoc-style block comments on optional/loose fields in `apps/web/src/types.ts` (`RetrievalDebugChunk` metadata)
- Python relies on docstrings on key orchestrators (`run_study_question`, `ingest_document`) — not every helper

## Function Design

**Size:**
- Keep route handlers thin: delegate to `run_study_query` / `compute_topic_frequency` in `apps/api/app/main.py`
- Retrieval module `apps/api/app/services/rag/retrieve.py` is large — add new behavior as focused helpers (`section_page_hints`, `_rrf_fuse`) rather than expanding monolith functions

**Parameters:**
- Prefer explicit keyword args for pipeline entrypoints: `course_id`, `question`, `preset`, `debug`
- FastAPI bodies use Pydantic models with `Field(min_length=1)` for validation
- Settings accessed via singleton `settings` from `apps/api/app/config.py` — avoid passing config through deep call stacks unless testing

**Return values:**
- HTTP: Pydantic models or `dict` for simple endpoints (`health` returns `{"status": "ok"}`)
- Pipeline: `@dataclass` results with explicit `status` field
- Eval/replay: JSON-serializable `dict` rows written to `eval/reports/latest.jsonl`

## Module Design

**Exports:**
- Python packages use implicit namespace packages under `app/`; no heavy `__init__.py` re-exports
- TypeScript: named exports per file; no barrel `index.ts` in `apps/web/src/`

**Barrel files:**
- Not used in web or API application code

**Layering (prescriptive):**
| Layer | Location | Responsibility |
|-------|----------|----------------|
| Routes | `apps/api/app/main.py` | HTTP, Pydantic contracts, exception mapping |
| Orchestration | `apps/api/app/services/rag/pipeline.py` | retrieve → rerank → gate → generate |
| Domain services | `apps/api/app/services/rag/*.py`, `ingestion.py`, `chunker/` | Algorithms and DB access |
| Models | `apps/api/app/models.py` | SQLAlchemy tables |
| Config | `apps/api/app/config.py` | `pydantic_settings` + retrieval thresholds |

**Agent ownership (from `AGENTS.md`):**
- One file, one owner during parallel phases — do not edit forbidden paths listed in the ownership table
- Shared read-only: `eval/golden_set.jsonl`, `docs/failures-checklist.md`, `docs/api-contracts.md`

**Web architecture:**
- Presentational components receive props + callbacks (`apps/web/src/components/QueryForm.tsx`)
- Side effects and fetch in hooks (`apps/web/src/hooks/useStudyQuery.ts`)
- API boundary isolated in `apps/web/src/api/queryClient.ts`
- Vite dev proxy in `apps/web/vite.config.ts` forwards `/api` and `/health` to `http://localhost:8001`

**Eval alignment:**
- Page tolerance logic duplicated intentionally: `apps/web/src/utils/pageMatch.ts` mirrors `eval/score_precision.py` `page_hit` (±1 page) — keep in sync when changing scoring rules

---

*Convention analysis: 2026-05-30*
